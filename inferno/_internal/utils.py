from collections.abc import Iterable, Iterator
from functools import reduce
import torch
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def fzip(
    seq: Iterable[T], *fns: Callable[[T], T], identity: bool = True
) -> Iterator[tuple[T, ...]]:
    r"""Applies functions to an iterable.

    The specified functions ``fns`` should be side-effect free. They will be processed
    in the order given and applied in order to ``seq`` should they be stateful.

    Args:
        seq (Iterable[T]): sequence to which functions will be applied.
        *fns (Callable[[T], T]): functions to apply.
        identity (bool, optional): if the output of the identity function should be
            prepended to each output tuple. Defaults to True.

    Yields:
        tuple[T, ...]: results of the functions applied to the sequence.
    """
    # prepend identity function if requested
    if identity:
        fns = (lambda x: x,) + fns

    # iterate and apply
    for e in seq:
        yield tuple(fn(e) for fn in fns)


def unique(seq: Iterable[T], ids: bool = True) -> Iterator[T]:
    r"""Filters non-unique elements in an iterable.

    Underneath this uses a hash set for testing equality. By default, the memory
    location of objects, ``id(obj)`` is used and therefore tests by identity. When
    ``ids`` is set to ``False``, this acts like a lazily evaluated ``set()`` call.

    Args:
        seq (Iterable[T]): sequence of elements to filter.
        ids (bool, optional): if object ids should be used for testing presence.
            Defaults to True.

    Yields:
        T: unique elements in the iterable.
    """
    # set of found elements
    found = set()

    # filter by hash equality (using integer id as key if ids)
    for elem, key in fzip(seq, (lambda e: id(e)) if ids else (lambda e: e)):
        if key not in found:
            found.add(key)
            yield elem


class Proxy:
    r"""Controlls access to nested members.

    This prevents overwriting class attributes sent this way and can remap attributes.
    The following example.

    .. code-block:: python

            self.layers = nn.ModuleDict()
            self.layers["linear"] = nn.Linear(784, 10)

            @property
            def weight(self):
                return Proxy(self.layers, 'linear')

    When the user calls the ``weight`` property of that object, it returns a proxy
    which will intercept any ``__getattr__`` calls and postpend the accessor. The
    returned value of that call can then be put chained with other proxies for more
    complex logic.

    Args:
        inner (Any): object to wrap.
        firstacc (str | None): top level proxy attribute.
        *otheracc (str | None): additional proxy attributes.

    Note:
        Each accessor can be a dot-seperated string of attributes.
    """

    def __init__(self, inner: Any, firstacc: str | None, *otheracc: str | None):
        self.inner = inner
        self.firstacc = firstacc
        self.otheracc = otheracc

    def __getattr__(self, attr: str) -> Any:
        # first proxy step
        if self.firstacc:
            res = rgetattr(self.inner, attr + "." + self.firstacc)
        else:
            res = rgetattr(self.inner, attr)

        # optionally chain proxies
        if self.otheracc:
            return Proxy(res, self.otheracc[0], self.otheracc[1:])
        else:
            return res


def regroup(
    flatseq: tuple[Any, ...], groups: tuple[int | tuple, ...]
) -> tuple[Any, ...]:
    return tuple(
        flatseq[g] if isinstance(g, int) else regroup(flatseq, g) for g in groups
    )


def newtensor(obj: Any) -> torch.Tensor:
    r"""Creates a new tensor from an existing object, tensor or otherwise.

    Args:
        obj (Any): object off of which new tensor should be constructed.

    Returns:
       torch.Tensor: newly constructed tensor.
    """
    try:
        return obj.clone().detach()
    except AttributeError:
        return torch.tensor(obj)


def rgetattr(obj: object, attr: str, *default) -> Any:
    r"""Accesses and returns an object attribute recursively using dot notation.

    For example, if we have an object ``obj`` and a string ``"so1.so2.so3"``,
    this function will retrieve ``obj.so1.so2.so3``. This is performed recursively
    using ``getattr()``.

    Args:
        obj (object): object from which to retrieve the nested attribute.
        attr (str): string in dot notation for the nested attribute to retrieve,
            excluding the initial dot.
        *default (Any, optional): if specified, including with None, it will be
            returned if attr is not found.

    Returns:
        Any: nested attribute of ``obj`` specified by ``attr``,
        or ``default`` if it is specified and ``attr`` is not found.

    Note:
        If a default is specified, it will be returned if at any point in the chain,
        the attribute is not found. If multiple values are passed with ``*default``,
        only the first will be used.
    """

    try:
        return reduce(getattr, [obj] + attr.split("."))

    except AttributeError:
        if default:
            return default[0]
        else:
            raise


def rsetattr(obj: object, attr: str, val: Any):
    r"""Sets an object attribute recursively using dot notation.

    For example, if we have an object ``obj`` and a string ``"so1.so2.so3"``,
    to which some value ``v`` is being assigned, this function will retrieve
    ``obj.so1.so2`` recursively using ``getattr()``,  then assign ``v`` to ``so3``
    in the object ``so2`` using ``setattr()``.

    Args:
        obj (object): object to which the nested attribute will be set.
        attr (str): string in dot notation for the nested attribute to set,
            excluding the initial dot.
        val (Any): value to which the attribute will be set.
    """
    pre, _, post = attr.rpartition(".")
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)
