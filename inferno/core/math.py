import cmath
import einops as ein
import functools
import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


@functools.singledispatch
def exp(
    x: int | float | complex | torch.Tensor | np.ndarray | np.number,
) -> float | complex | torch.Tensor | np.ndarray | np.number:
    r"""Type agnostic exponential function.

    .. math::
        y = e^x

    Args:
        x (int | float | complex | torch.Tensor | numpy.ndarray | numpy.number): value
            by which to raise :math:`e`.

    Returns:
        float | complex | torch.Tensor | numpy.ndarray | numpy.number: :math:`e`
        raised to the input.
    """
    raise NotImplementedError


@exp.register(int)
@exp.register(float)
def _(x: int | float) -> float:
    return math.exp(x)


@exp.register(complex)
def _(x: complex) -> complex:
    return cmath.exp(x)


@exp.register(torch.Tensor)
def _(x: torch.Tensor) -> torch.Tensor:
    return torch.exp(x)


@exp.register(np.ndarray)
def _(x: np.ndarray) -> np.ndarray:
    return np.exp(x)


@exp.register(np.number)
def _(x: np.number) -> np.number:
    return np.exp(x)


@functools.singledispatch
def sqrt(
    x: int | float | complex | torch.Tensor | np.ndarray | np.number,
) -> float | complex | torch.Tensor | np.ndarray | np.number:
    r"""Type agnostic square root function.

    .. math::
        y = \sqrt{x}

    Args:
        x (int | float | complex | torch.Tensor | numpy.ndarray | numpy.number): value
            of which to take the square root.

    Returns:
        float | complex | torch.Tensor | numpy.ndarray | numpy.number: square root of
        the input.
    """
    raise NotImplementedError


@sqrt.register(int)
@sqrt.register(float)
def _(x: int | float) -> float:
    return math.sqrt(x)


@sqrt.register(complex)
def _(x: complex) -> complex:
    return cmath.sqrt(x)


@sqrt.register(torch.Tensor)
def _(x: torch.Tensor) -> torch.Tensor:
    return torch.sqrt(x)


@sqrt.register(np.ndarray)
def _(x: np.ndarray) -> np.ndarray:
    return np.sqrt(x)


@sqrt.register(np.number)
def _(x: np.number) -> np.number:
    return np.sqrt(x)


def normalize(
    data: torch.Tensor,
    order: int | float,
    scale: float | complex = 1.0,
    dim: int | tuple[int] | None = None,
    epsilon: float = 1e-12,
) -> torch.Tensor:
    r"""Normalizes a tensor.

    Args:
        data (torch.Tensor): data to normalize.
        order (int | float): order of :math:`p`-norm by which to normalize.
        scale (float | complex, optional): desired :math:`p`-norm of elements along
            specified dimensions. Defaults to 1.0.
        dim (int | tuple[int] | None, optional): dimension(s) along which to normalize,
            all dimensions if None. Defaults to None.
        epsilon (float, optional): value added to the demoninator in case of
            zero-valued norms. Defaults to 1e-12.

    Returns:
        torch.Tensor: normalized tensor.
    """
    return scale * F.normalize(data, p=order, dim=dim, eps=epsilon)


def rescale(
    data: torch.Tensor,
    resmin: int | float | torch.Tensor | None,
    resmax: int | float | torch.Tensor | None,
    *,
    srcmin: int | float | torch.Tensor | None = None,
    srcmax: int | float | torch.Tensor | None = None,
    dim: int | tuple[int, ...] | None = None,
) -> torch.Tensor:
    r"""Rescales a tensor (min-max normalization).

    Args:
        data (torch.Tensor): tensor to rescale.
        resmin (int | float | torch.Tensor | None): minimum value for the
            tensor after rescaling, unchanged if None.
        resmax (int | float | torch.Tensor | None): maximum value for the
            tensor after rescaling, unchanged if None.
        srcmin (int | float | torch.Tensor | None, optional): minimum value for the
            tensor before rescaling, computed if None. Defaults to None.
        srcmax (int | float | torch.Tensor | None, optional): maximum value for the
            tensor before rescaling, computed if None. Defaults to None.
        dim (int | tuple[int, ...] | None, optional): dimension(s) along which amin/amax
            are computed if not provided, all dimensions if None. Defaults to None.

    Returns:
        torch.Tensor: rescaled tensor.
    """
    # perform substitutions
    if srcmin is None:
        srcmin = torch.amin(data, dim=dim, keepdim=True)
    if srcmax is None:
        srcmax = torch.amax(data, dim=dim, keepdim=True)
    if resmin is None:
        resmin = srcmin
    if resmax is None:
        resmax = srcmax

    # rescale and return
    return srcmin + (((data - srcmin) * (resmax - resmin)) / (srcmax - srcmin))


def exponential_smoothing(
    obs: torch.Tensor,
    level: torch.Tensor | None,
    *,
    alpha: float | int | complex | torch.Tensor,
) -> torch.Tensor:
    r"""Performs simple exponential smoothing for a time step.

    .. math::
        \begin{align*}
            s_0 &= x_0 \\
            s_{t + 1} &= \alpha x_{t + 1}  + (1 - \alpha) s_t
        \end{align*}

    Args:
        obs (torch.Tensor): latest state to consider for exponential smoothing,
            :math:`x`.
        level (torch.Tensor | None): current value of the smoothed level,
            :math:`s`.
        alpha (float | int | complex | torch.Tensor): level smoothing factor,
            :math:`\alpha`.

    Returns:
        torch.Tensor: revised exponentially smoothed value.
    """
    # initial condition
    if level is None:
        return obs

    # standard condition
    else:
        return alpha * obs + (1 - alpha) * level


def holt_linear_smoothing(
    obs: torch.Tensor,
    level: torch.Tensor | None,
    trend: torch.Tensor | None,
    *,
    alpha: float | int | complex | torch.Tensor,
    beta: float | int | complex | torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    r"""Performs Holt linear smoothing for a time step.

    .. math::
        \begin{align*}
            s_0 &= x_0 \\
            b_0 &= x_1 - x_0 \\
            s_{t + 1} &= \alpha x_{t + 1}  + (1 - \alpha) s_t \\
            b_{t + 1} &= \beta (s_{t + 1} - s_t) + (1 - \beta) b_t
        \end{align*}

    Args:
        obs (torch.Tensor): latest state to consider for exponential smoothing,
            :math:`x_{t + 1}`.
        level (torch.Tensor | None): current value of the smoothed level,
            :math:`s`.
        trend (torch.Tensor | None): current value of the smoothed trend,
            :math:`b`.
        alpha (float | int | complex | torch.Tensor): level smoothing factor,
            :math:`\alpha`.
        beta (float | int | complex | torch.Tensor): trend smoothing factor,
            :math:`\beta`.

    Returns:
        tuple[torch.Tensor, int | torch.Tensor]: tuple containing output/updated state:

            level: revised exponentially smoothed level.

            trend: revised exponentially smoothed trend.
    """
    # t=0 condition
    if level is None:
        return obs, None

    # t=1 condition (initialize trend as x1-x0)
    if trend is None:
        trend = obs - level

    # t>0 condition
    s = exponential_smoothing(obs, level + trend, alpha)
    b = exponential_smoothing(s - level, trend, beta)

    return s, b


def isi(
    spikes: torch.Tensor, step_time: float | None = None, time_first: bool = False
) -> torch.Tensor:
    r"""Transforms spike trains into inter-spike intervals.

    The returned tensor will be padded with ``NaN``s where an interval could not
    be computed but the position existed (e.g. padding at the end of) spike trains
    with fewer spikes. If no intervals could be generated at all, a tensor with a
    final dimension of zero will be returned.

    Args:
        spikes (torch.Tensor): spike trains for which to calculate intervals.
        step_time (float | None, optional): length of the simulation step,
            in :math:`\text{ms}`, if None returned intervals will be as a multiple
            of simulation steps. Defaults to None.
        time_first (bool, optional): if the time dimension is given first rather than
            last. Defaults to False.

    Returns:
        torch.Tensor: interspike intervals for the given spike trains.

    .. admonition:: Shape
        :class: tensorshape

        ``spikes``:

        :math:`N_0 \times \cdots \times T` or :math:`T \times N_0 \times \cdots`

        ``return``:

        :math:`N_0 \times \cdots \times (C - 1)` or :math:`(C - 1) \times N_0 \times \cdots`

        Where:
            * :math:`N_0, \ldots` shape of the generating population (batch, neuron shape, etc).
            * :math:`T` the length of the spike trains.
            * :math:`C` the maximum number of spikes amongst the spike trains.
    """
    # bring time dimension to the end if it is not
    if time_first:
        spikes = ein.rearrange(spikes, "t ... -> ... t")

    # set dummy step time if required
    step_time = 1.0 if step_time is None else float(step_time)

    # pad spikes with true to ensure at least one (req. for split)
    padded = F.pad(spikes, (1, 0), mode="constant", value=True)

    # compute nonzero values
    nz = torch.nonzero(padded)[..., -1]

    # compute split indices (at the added pads)
    splits = torch.nonzero(torch.logical_not(nz)).view(-1).tolist()[1:]

    # split the tensor into various length subtensors (subtract 1 to unshift)
    intervals = torch.tensor_split((nz - 1) * step_time, splits, dim=-1)

    # stack, pad trailing with nan, trim leading pad
    intervals = nn.utils.rnn.pad_sequence(
        intervals, batch_first=True, padding_value=float("nan")
    )[:, 1:]

    # compute intervals
    intervals = torch.diff(intervals, dim=-1)

    # reshape and return
    if time_first:
        return ein.rearrange(intervals.view(*spikes.shape[:-1], -1), "... t -> t ...")
    else:
        return intervals.view(*spikes.shape[:-1], -1)