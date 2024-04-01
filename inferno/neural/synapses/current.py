from .mixins import SpikeCurrentMixin, SpikeDerivedCurrentMixin
from ..base import InfernoSynapse, SynapseConstructor
from ..._internal import argtest
from ...functional import interp_nearest, interp_previous
import torch
from typing import Literal


class DeltaCurrent(SpikeDerivedCurrentMixin, InfernoSynapse):
    r"""Memoryless synapse which responds instantaneously to input.

    .. math::
        I(t) =
        \begin{cases}
            Q / \Delta t & \text{presynaptic spike}
            0 & \text{otherwise}
        \end{cases}

    Args:
        shape (tuple[int, ...] | int): shape of the group of synapses being simulated.
        step_time (float): length of a simulation time step, in :math:`\text{ms}`.
        spike_q (float): charge carried by each presynaptic spike, in :math:`\text{pC}`.
        delay (float, optional): maximum supported delay, in :math:`\text{ms}`.
        interp_mode (Literal["nearest", "previous"], optional): interpolation mode
            for selectors between observations. Defaults to "nearest".
        interp_tol (float, optional): maximum difference in time from an observation
            to treat as co-occurring, in :math:`\text{ms}`. Defaults to 0.0.
        current_overbound (float | None, optional): value to replace currents out of
            bounds, uses values at observation limits if None. Defaults to 0.0.
        spike_overbound (bool | None, optional): value to replace spikes out of bounds,
            uses values at observation limits if None. Defaults to False.
        batch_size (int, optional): size of input batches for simualtion. Defaults to 1.

    See Also:
        For more details and references, visit
        :ref:`zoo/synapses-current:Delta (CUBA Variant)` in the zoo.
    """

    def __init__(
        self,
        shape: tuple[int, ...] | int,
        step_time: float,
        *,
        spike_q: float,
        delay: float = 0.0,
        interp_mode: Literal["nearest", "previous"] = "previous",
        interp_tol: float = 0.0,
        current_overbound: float | None = 0.0,
        spike_overbound: bool | None = False,
        batch_size: int = 1,
    ):
        # call superclass constructor
        InfernoSynapse.__init__(self, shape, step_time, delay, batch_size)

        # synapse attributes
        self.spike_q = argtest.neq("spike_q", spike_q, 0, float)

        match interp_mode.lower():
            case "nearest":
                interp = interp_nearest
            case "previous":
                interp = interp_previous
            case _:
                raise RuntimeError(
                    f"invalid interp_mode '{interp_mode}' received, must be one of "
                    "'nearest' or 'previous'."
                )

        # call mixin constructor
        SpikeDerivedCurrentMixin.__init__(
            self,
            torch.zeros(*self.batchedshape, dtype=torch.bool),
            "_to_current",
            current_interp=interp,
            current_interp_kwargs={},
            spike_interp=interp,
            spike_interp_kwargs={},
            current_overbound=current_overbound,
            spike_overbound=spike_overbound,
            tolerance=interp_tol,
        )

    @classmethod
    def partialconstructor(
        cls,
        spike_q: float,
        interp_mode: Literal["nearest", "previous"] = "previous",
        interp_tol: float = 0.0,
        current_overbound: float | None = 0.0,
        spike_overbound: bool | None = False,
    ) -> SynapseConstructor:
        r"""Returns a function with a common signature for synapse construction.

        Args:
            spike_q (float): charge carried by each presynaptic spike,
                in :math:`\text{pC}`.
            interp_mode (Literal["nearest", "previous"], optional): interpolation mode
                for selectors between observations. Defaults to "nearest".
            interp_tol (float, optional): maximum difference in time from an observation
                to treat as co-occurring, in :math:`\text{ms}`. Defaults to 0.0.
            current_overbound (float | None, optional): value to replace currents out of
                bounds, uses values at observation limits if None. Defaults to 0.0.
            spike_overbound (bool | None, optional): value to replace spikes out of
                bounds, uses values at observation limits if None. Defaults to False.

        Returns:
           SynapseConstructor: partial constructor for synapse.
        """

        def constructor(
            shape: tuple[int, ...] | int,
            step_time: float,
            delay: float,
            batch_size: int,
        ):
            return cls(
                shape=shape,
                step_time=step_time,
                spike_q=spike_q,
                delay=delay,
                interp_mode=interp_mode,
                interp_tol=interp_tol,
                current_overbound=current_overbound,
                spike_overbound=spike_overbound,
                batch_size=batch_size,
            )

        return constructor

    def _to_current(self, spikes: torch.Tensor) -> torch.Tensor:
        r"""Used internally, converts spikes to currents.

        Args:
            spikes (torch.Tensor): input spikes.

        Returns:
            torch.Tensor: synaptic current at the time of the provided input spikes.
        """
        return spikes * (self.spike_q / self.dt)

    def clear(self, **kwargs):
        r"""Resets synapses to their resting state."""
        self.spike_.reset(False)

    def forward(self, *inputs: torch.Tensor, **kwargs) -> torch.Tensor:
        r"""Runs a simulation step of the synaptic dynamics.

        Args:
            *inputs (torch.Tensor): input spikes to the synapse.

        Returns:
            torch.Tensor: synaptic currents after simulation step.

        Important:
            Only the first tensor of ``*inputs`` will be used.
        """
        self.spike = inputs[0]
        return self.current


class DeltaPlusCurrent(SpikeCurrentMixin, InfernoSynapse):
    r"""Memoryless synapse which responds instantaneously to input, with passthrough current.

    .. math::
        I(t) =
        \begin{cases}
            Q / \Delta t + I_x & \text{presynaptic spike}
            I_x & \text{otherwise}
        \end{cases}

    Args:
        shape (tuple[int, ...] | int): shape of the group of synapses being simulated.
        step_time (float): length of a simulation time step, in :math:`\text{ms}`.
        spike_q (float): charge carried by each presynaptic spike, in :math:`\text{pC}`.
        delay (float, optional): maximum supported delay, in :math:`\text{ms}`.
        interp_mode (Literal["nearest", "previous"], optional): interpolation mode
            for selectors between observations. Defaults to "nearest".
        interp_tol (float, optional): maximum difference in time from an observation
            to treat as co-occurring, in :math:`\text{ms}`. Defaults to 0.0.
        current_overbound (float | None, optional): value to replace currents out of
            bounds, uses values at observation limits if None. Defaults to 0.0.
        spike_overbound (bool | None, optional): value to replace spikes out of bounds,
            uses values at observation limits if None. Defaults to False.
        batch_size (int, optional): size of input batches for simualtion. Defaults to 1.

    See Also:
        For more details and references, visit
        :ref:`zoo/synapses-current:Delta (CUBA Variant)` in the zoo.
    """

    def __init__(
        self,
        shape: tuple[int, ...] | int,
        step_time: float,
        *,
        spike_q: float,
        delay: float = 0.0,
        interp_mode: Literal["nearest", "previous"] = "previous",
        interp_tol: float = 0.0,
        current_overbound: float | None = 0.0,
        spike_overbound: bool | None = False,
        batch_size: int = 1,
    ):
        # call superclass constructor
        InfernoSynapse.__init__(self, shape, step_time, delay, batch_size)

        # synapse attributes
        self.spike_q = argtest.neq("spike_q", spike_q, 0, float)

        match interp_mode.lower():
            case "nearest":
                interp = interp_nearest
            case "previous":
                interp = interp_previous
            case _:
                raise RuntimeError(
                    f"invalid interp_mode '{interp_mode}' received, must be one of "
                    "'nearest' or 'previous'."
                )

        # call mixin constructor
        SpikeCurrentMixin.__init__(
            self,
            torch.zeros(*self.batchedshape),
            torch.zeros(*self.batchedshape, dtype=torch.bool),
            current_interp=interp,
            current_interp_kwargs={},
            spike_interp=interp,
            spike_interp_kwargs={},
            current_overbound=current_overbound,
            spike_overbound=spike_overbound,
            tolerance=interp_tol,
        )

    @classmethod
    def partialconstructor(
        cls,
        spike_q: float,
        interp_mode: Literal["nearest", "previous"] = "previous",
        interp_tol: float = 0.0,
        current_overbound: float | None = 0.0,
        spike_overbound: bool | None = False,
    ) -> SynapseConstructor:
        r"""Returns a function with a common signature for synapse construction.

        Args:
            spike_q (float): charge carried by each presynaptic spike,
                in :math:`\text{pC}`.
            interp_mode (Literal["nearest", "previous"], optional): interpolation mode
                for selectors between observations. Defaults to "nearest".
            interp_tol (float, optional): maximum difference in time from an observation
                to treat as co-occurring, in :math:`\text{ms}`. Defaults to 0.0.
            current_overbound (float | None, optional): value to replace currents out of
                bounds, uses values at observation limits if None. Defaults to 0.0.
            spike_overbound (bool | None, optional): value to replace spikes out of
                bounds, uses values at observation limits if None. Defaults to False.

        Returns:
           SynapseConstructor: partial constructor for synapse.
        """

        def constructor(
            shape: tuple[int, ...] | int,
            step_time: float,
            delay: float,
            batch_size: int,
        ):
            return cls(
                shape=shape,
                step_time=step_time,
                spike_q=spike_q,
                delay=delay,
                interp_mode=interp_mode,
                interp_tol=interp_tol,
                current_overbound=current_overbound,
                spike_overbound=spike_overbound,
                batch_size=batch_size,
            )

        return constructor

    def clear(self, **kwargs):
        r"""Resets synapses to their resting state."""
        self.spike_.reset(False)
        self.current_.reset(0.0)

    def forward(self, *inputs: torch.Tensor, **kwargs) -> torch.Tensor:
        r"""Runs a simulation step of the synaptic dynamics.

        Args:
            *inputs (torch.Tensor): input spikes to the synapse.

        Returns:
            torch.Tensor: synaptic currents after simulation step.

        Important:
            The first tensor of ``*inputs`` will represent the input spikes. Any
            subsequent tensors will be treated as injected current. These must be
            broadcastable with :py:attr:`current`.
        """
        self.spike = inputs[0].bool()
        self.current = sum((inputs[0] * (self.spike_q / self.dt), *inputs[1:]))
        return self.current
