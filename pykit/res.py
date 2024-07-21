from __future__ import annotations
import functools
import inspect
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Final,
    Generator,
    Generic,
    Iterator,
    Literal,
    NoReturn,
    ParamSpec,
    Type,
    TypeAlias,
    TypeGuard,
    TypeVar,
    Union,
)
from warnings import warn

from pykit.err import ValErr

__all__ = [
    "Ok",
    "Err",
    "Result",
    "Res",
    "OkErr",
    "UnwrapErr",
    "as_async_result",
    "as_result",
    "is_ok",
    "is_err",
    "do",
    "do_async",
    "throw_err_val",
    "resultify",
]


T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)  # Success type
E = TypeVar("E", covariant=True)  # Error type
U = TypeVar("U")
F = TypeVar("F")
P = ParamSpec("P")
R = TypeVar("R")
TBE = TypeVar("TBE", bound=BaseException)


class Ok(Generic[T_co]):
    """
    A value that indicates success and which stores arbitrary data for the return value.
    """

    __match_args__ = ("ok_value",)
    __slots__ = ("_value",)

    def __iter__(self) -> Iterator[T_co]:
        yield self._value

    def __init__(self, value: T_co) -> None:
        self._value = value

    def __repr__(self) -> str:
        return f"Ok({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ok) and self._value == other._value

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __hash__(self) -> int:
        return hash((True, self._value))

    def is_ok(self) -> Literal[True]:
        return True

    def is_err(self) -> Literal[False]:
        return False

    def ok(self) -> T_co:
        """
        Return the value.
        """
        return self._value

    def err(self) -> None:
        """
        Return `None`.
        """
        return

    @property
    def value(self) -> T_co:
        """
        Return the inner value.

        @deprecated Use `ok_value` or `err_value` instead. This method will be
        removed in a future version.
        """
        warn(
            "Accessing `.value` on Result type is deprecated, please use "
            + "`.ok_value` or `.err_value` instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._value

    @property
    def ok_value(self) -> T_co:
        """
        Return the inner value.
        """
        return self._value

    def expect(self, _message: str) -> T_co:
        """
        Return the value.
        """
        return self._value

    def expect_err(self, message: str) -> NoReturn:
        """
        Raise an UnwrapErr since this type is `Ok`
        """
        raise UnwrapErr(self, message)

    def unwrap(self) -> T_co:
        """
        Return the value.
        """
        return self._value

    def unwrap_err(self) -> NoReturn:
        """
        Raise an UnwrapErr since this type is `Ok`
        """
        raise UnwrapErr(self, "Called `Result.unwrap_err()` on an `Ok` value")

    def unwrap_or(self, _default: object) -> T_co:
        """
        Return the value.
        """
        return self._value

    def unwrap_or_else(self, op: object) -> T_co:
        """
        Return the value.
        """
        return self._value

    def unwrap_or_raise(self, e: object) -> T_co:
        """
        Return the value.
        """
        return self._value

    def map(self, op: Callable[[T_co], U]) -> Ok[U]:
        """
        The contained result is `Ok`, so return `Ok` with original value mapped to
        a new value using the passed in function.
        """
        return Ok(op(self._value))

    async def map_async(
        self, op: Callable[[T_co], Awaitable[U]],
    ) -> Ok[U]:
        """
        The contained result is `Ok`, so return the result of `op` with the
        original value passed in
        """
        return Ok(await op(self._value))

    def map_or(self, default: object, op: Callable[[T_co], U]) -> U:
        """
        The contained result is `Ok`, so return the original value mapped to a new
        value using the passed in function.
        """
        return op(self._value)

    def map_or_else(self, default_op: object, op: Callable[[T_co], U]) -> U:
        """
        The contained result is `Ok`, so return original value mapped to
        a new value using the passed in `op` function.
        """
        return op(self._value)

    def map_err(self, op: object) -> Ok[T_co]:
        """
        The contained result is `Ok`, so return `Ok` with the original value
        """
        return self

    def and_then(self, op: Callable[[T_co], Result[U, E]]) -> Result[U, E]:
        """
        The contained result is `Ok`, so return the result of `op` with the
        original value passed in
        """
        return op(self._value)

    async def and_then_async(
        self, op: Callable[[T_co], Awaitable[Result[U, E]]],
    ) -> Result[U, E]:
        """
        The contained result is `Ok`, so return the result of `op` with the
        original value passed in
        """
        return await op(self._value)

    def or_else(self, op: object) -> Ok[T_co]:
        """
        The contained result is `Ok`, so return `Ok` with the original value
        """
        return self

    def inspect(self, op: Callable[[T_co], Any]) -> Result[T_co, E]:
        """
        Calls a function with the contained value if `Ok`. Returns the original result.
        """
        op(self._value)
        return self

    def inspect_err(self, op: Callable[[E], Any]) -> Result[T_co, E]:
        """
        Calls a function with the contained value if `Err`. Returns the original result.
        """
        return self

    def eject(self) -> T_co:
        """
        Same as unwrap, but, instead of UnwrapErr, raises the original err value
        of Res.
        """
        return _eject(self)

    def _ignore(self):
        """
        Used to signify that the result intentially ignored.

        Useful to avoid linter errors on intentional behaviour.
        """
        _ignore(self)


class DoException(Exception):
    """
    This is used to signal to `do()` that the result is an `Err`,
    which short-circuits the generator and returns that Err.
    Using this exception for control flow in `do()` allows us
    to simulate `and_then()` in the Err case: namely, we don't call `op`,
    we just return `self` (the Err).
    """

    def __init__(self, err: Err[E]) -> None:
        self.err = err


class Err(Generic[E]):
    """
    A value that signifies failure and which stores arbitrary data for the error.
    """

    __match_args__ = ("err_value",)
    __slots__ = ("_value",)

    def __iter__(self) -> Iterator[NoReturn]:
        def _iter() -> Iterator[NoReturn]:
            # Exception will be raised when the iterator is advanced, not when it's created
            raise DoException(self)
            yield  # This yield will never be reached, but is necessary to create a generator

        return _iter()

    def __init__(self, value: E) -> None:
        self._value = value

    def __repr__(self) -> str:
        return f"Err({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Err) and self._value == other._value

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __hash__(self) -> int:
        return hash((False, self._value))

    def is_ok(self) -> Literal[False]:
        return False

    def is_err(self) -> Literal[True]:
        return True

    def ok(self) -> None:
        """
        Return `None`.
        """
        return

    def err(self) -> E:
        """
        Return the error.
        """
        return self._value

    @property
    def value(self) -> E:
        """
        Return the inner value.

        @deprecated Use `ok_value` or `err_value` instead. This method will be
        removed in a future version.
        """
        warn(
            "Accessing `.value` on Result type is deprecated, please use "
            + "`.ok_value` or '.err_value' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._value

    @property
    def err_value(self) -> E:
        """
        Return the inner value.
        """
        return self._value

    def expect(self, message: str) -> NoReturn:
        """
        Raises an `UnwrapErr`.
        """
        exc = UnwrapErr(
            self,
            f"{message}: {self._value!r}",
        )
        if isinstance(self._value, BaseException):
            raise exc from self._value
        raise exc

    def expect_err(self, _message: str) -> E:
        """
        Return the inner value
        """
        return self._value

    def unwrap(self) -> NoReturn:
        """
        Raises an `UnwrapErr`.
        """
        exc = UnwrapErr(
            self,
            f"Called `Result.unwrap()` on an `Err` value: {self._value!r}",
        )
        if isinstance(self._value, BaseException):
            raise exc from self._value
        raise exc

    def unwrap_err(self) -> E:
        """
        Return the inner value
        """
        return self._value

    def unwrap_or(self, default: U) -> U:
        """
        Return `default`.
        """
        return default

    def unwrap_or_else(self, op: Callable[[E], T_co]) -> T_co:
        """
        The contained result is ``Err``, so return the result of applying
        ``op`` to the error value.
        """
        return op(self._value)

    def unwrap_or_raise(self, e: Type[TBE]) -> NoReturn:
        """
        The contained result is ``Err``, so raise the exception with the value.
        """
        raise e(self._value)

    def map(self, op: object) -> Err[E]:
        """
        Return `Err` with the same value
        """
        return self

    async def map_async(self, op: object) -> Err[E]:
        """
        The contained result is `Ok`, so return the result of `op` with the
        original value passed in
        """
        return self

    def map_or(self, default: U, op: object) -> U:
        """
        Return the default value
        """
        return default

    def map_or_else(self, default_op: Callable[[], U], op: object) -> U:
        """
        Return the result of the default operation
        """
        return default_op()

    def map_err(self, op: Callable[[E], F]) -> Err[F]:
        """
        The contained result is `Err`, so return `Err` with original error mapped to
        a new value using the passed in function.
        """
        return Err(op(self._value))

    def and_then(self, op: object) -> Err[E]:
        """
        The contained result is `Err`, so return `Err` with the original value
        """
        return self

    async def and_then_async(self, op: object) -> Err[E]:
        """
        The contained result is `Err`, so return `Err` with the original value
        """
        return self

    def or_else(self, op: Callable[[E], Result[T_co, F]]) -> Result[T_co, F]:
        """
        The contained result is `Err`, so return the result of `op` with the
        original value passed in
        """
        return op(self._value)

    def inspect(self, op: Callable[[T_co], Any]) -> Result[T_co, E]:
        """
        Calls a function with the contained value if `Ok`. Returns the original result.
        """
        return self

    def inspect_err(self, op: Callable[[E], Any]) -> Result[T_co, E]:
        """
        Calls a function with the contained value if `Err`. Returns the original result.
        """
        op(self._value)
        return self

    def eject(self) -> NoReturn:
        """
        Same as unwrap, but, instead of UnwrapErr, raises the original err value
        of Res.
        """
        _eject(self)
        # shouldn't get to this point
        raise AssertionError

    def _ignore(self):
        """
        Used to signify that the result intentially ignored.

        Useful to avoid linter errors on intentional behaviour.
        """
        _ignore(self)


# define Result as a generic type alias for use
# in type annotations
"""
A simple `Result` type inspired by Rust.
Not all methods (https://doc.rust-lang.org/std/result/enum.Result.html)
have been implemented, only the ones that make sense in the Python context.
"""
Result: TypeAlias = Union[Ok[T_co], Err[E]]

"""
A type to use in `isinstance` checks.
This is purely for convenience sake, as you could also just write `isinstance(res, (Ok, Err))
"""
OkErr: Final = (Ok, Err)


class UnwrapErr(Exception):
    """
    Exception raised from ``.unwrap_<...>`` and ``.expect_<...>`` calls.

    The original ``Result`` can be accessed via the ``.result`` attribute, but
    this is not intended for regular use, as type information is lost:
    ``UnwrapErr`` doesn't know about both ``T`` and ``E``, since it's raised
    from ``Ok()`` or ``Err()`` which only knows about either ``T`` or ``E``,
    not both.
    """

    _result: Result[object, object]

    def __init__(self, result: Result[object, object], message: str) -> None:
        self._result = result
        super().__init__(message)

    @property
    def result(self) -> Result[Any, Any]:
        """
        Returns the original result.
        """
        return self._result

    @staticmethod
    def code() -> str:
        return "unwrap_err"


def as_result(
    *exceptions: Type[TBE],
) -> Callable[[Callable[P, R]], Callable[P, Result[R, TBE]]]:
    """
    Make a decorator to turn a function into one that returns a ``Result``.

    Regular return values are turned into ``Ok(return_value)``. Raised
    exceptions of the specified exception type(s) are turned into ``Err(exc)``.
    """
    if not exceptions or not all(
        inspect.isclass(exception) and issubclass(exception, BaseException)
        for exception in exceptions
    ):
        raise TypeError("as_result() requires one or more exception types")

    def decorator(f: Callable[P, R]) -> Callable[P, Result[R, TBE]]:
        """
        Decorator to turn a function into one that returns a ``Result``.
        """

        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[R, TBE]:
            try:
                return Ok(f(*args, **kwargs))
            except exceptions as exc:
                return Err(exc)

        return wrapper

    return decorator


def as_async_result(
    *exceptions: Type[TBE],
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[Result[R, TBE]]]]:
    """
    Make a decorator to turn an async function into one that returns a ``Result``.
    Regular return values are turned into ``Ok(return_value)``. Raised
    exceptions of the specified exception type(s) are turned into ``Err(exc)``.
    """
    if not exceptions or not all(
        inspect.isclass(exception) and issubclass(exception, BaseException)
        for exception in exceptions
    ):
        raise TypeError("as_result() requires one or more exception types")

    def decorator(
        f: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[Result[R, TBE]]]:
        """
        Decorator to turn a function into one that returns a ``Result``.
        """

        @functools.wraps(f)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[R, TBE]:
            try:
                return Ok(await f(*args, **kwargs))
            except exceptions as exc:
                return Err(exc)

        return async_wrapper

    return decorator


def is_ok(result: Result[T_co, E]) -> TypeGuard[Ok[T_co]]:
    """A typeguard to check if a result is an Ok

    Usage:

    ``` python
    r: Result[int, str] = get_a_result()
    if is_ok(r):
        r   # r is of type Ok[int]
    elif is_err(r):
        r   # r is of type Err[str]
    ```

    """
    return result.is_ok()


def is_err(result: Result[T_co, E]) -> TypeGuard[Err[E]]:
    """A typeguard to check if a result is an Err

    Usage:

    ``` python
    r: Result[int, str] = get_a_result()
    if is_ok(r):
        r   # r is of type Ok[int]
    elif is_err(r):
        r   # r is of type Err[str]
    ```

    """
    return result.is_err()


def do(gen: Generator[Result[T_co, E], None, None]) -> Result[T_co, E]:
    """Do notation for Result (syntactic sugar for sequence of `and_then()` calls).


    Usage:

    ``` rust
    // This is similar to
    use do_notation::m;
    let final_result = m! {
        x <- Ok("hello");
        y <- Ok(True);
        Ok(len(x) + int(y) + 0.5)
    };
    ```

    ``` rust
    final_result: Result[float, int] = do(
            Ok(len(x) + int(y) + 0.5)
            for x in Ok("hello")
            for y in Ok(True)
        )
    ```

    NOTE: If you exclude the type annotation e.g. `Result[float, int]`
    your type checker might be unable to infer the return type.
    To avoid an error, you might need to help it with the type hint.
    """
    try:
        return next(gen)
    except DoException as e:
        out: Err[E] = e.err  # type: ignore
        return out
    except TypeError as te:
        # Turn this into a more helpful error message.
        # Python has strange rules involving turning generators involving `await`
        # into async generators, so we want to make sure to help the user clearly.
        if "'async_generator' object is not an iterator" in str(te):
            raise TypeError(
                "Got async_generator but expected generator."
                "See the section on do notation in the README.",
            )
        raise


async def do_async(
    gen: Union[Generator[Result[T_co, E], None, None], AsyncGenerator[Result[T_co, E], None]],
) -> Result[T_co, E]:
    """Async version of do. Example:

    ``` python
    final_result: Result[float, int] = await do_async(
        Ok(len(x) + int(y) + z)
            for x in await get_async_result_1()
            for y in await get_async_result_2()
            for z in get_sync_result_3()
        )
    ```

    NOTE: Python makes generators async in a counter-intuitive way.

    ``` python
    # This is a regular generator:
        async def foo(): ...
        do(Ok(1) for x in await foo())
    ```

    ``` python
    # But this is an async generator:
        async def foo(): ...
        async def bar(): ...
        do(
            Ok(1)
            for x in await foo()
            for y in await bar()
        )
    ```

    We let users try to use regular `do()`, which works in some cases
    of awaiting async values. If we hit a case like above, we raise
    an exception telling the user to use `do_async()` instead.
    See `do()`.

    However, for better usability, it's better for `do_async()` to also accept
    regular generators, as you get in the first case:

    ``` python
    async def foo(): ...
        do(Ok(1) for x in await foo())
    ```

    Furthermore, neither mypy nor pyright can infer that the second case is
    actually an async generator, so we cannot annotate `do_async()`
    as accepting only an async generator. This is additional motivation
    to accept either.
    """
    try:
        if isinstance(gen, AsyncGenerator):
            return await gen.__anext__()
        else:
            return next(gen)
    except DoException as e:
        out: Err[E] = e.err  # type: ignore
        return out

Res = Result[T_co, Exception]
"""
Short version of result.Result, where err value is always an Exception.
"""

def throw_err_val(fn: Callable):
    """
    Calls a func and raises Err.err_value if func returns it.
    """
    res = fn()
    if isinstance(res, Err):
        raise res.err_value

def resultify(
        fn: Callable[[], T_co],
        errs: tuple[type[Exception], ...] = (Exception,)) -> Res[T_co]:
    """
    Calls a func and wraps retval to Res - to Err on thrown exception, Ok
    otherwise.

    Useful to integrate non-result functions.
    """
    try:
        res = fn()
    except errs as err:
        return Err(err)
    return Ok(res)

def _eject(res: Res[T_co] | Result[T_co, Any]) -> T_co:
    """
    Same as unwrap, but, instead of UnwrapErr, raises the original err value
    of Res.

    If the original err_value is not an Exception, it will be raised as
    ValErr(str(res.err_value)).
    """
    if isinstance(res, Err):
        if isinstance(res.err_value, Exception):
            raise res.err_value
        raise ValErr(str(res.err_value))
    return res.ok_value

def _ignore(res: Res | Result):
    """
    Used to signify that the result intentially ignored.

    Useful to avoid linter errors on intentional behaviour.
    """
