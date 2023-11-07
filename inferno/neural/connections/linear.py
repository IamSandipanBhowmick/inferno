import einops as ein
from inferno.typing import OneToOne
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from .. import Connection, SynapseConstructor
from .._mixins import WeightBiasDelayMixin


class DenseLinear(WeightBiasDelayMixin, Connection):
    r"""Linear all-to-all connection.

    .. math::
        y = x W^\intercal + b

    Args:
        in_shape (tuple[int, ...] | int): expected shape of input tensor, excluding batch.
        out_shape (tuple[int, ...] | int): expected shape of output tensor, excluding batch.
        step_time (float): length of a simulation time step, in :math:`\mathrm{ms}`.
        synapse (SynapseConstructor): partial constructor for inner :py:class:`~inferno.neural.Synapse`.
        batch_size (int, optional): size of input batches for simualtion. Defaults to 1.
        bias (bool, optional): if the connection should include learnable additive bias. Defaults to False.
        delay (float | None, optional): length of time the connection should support delays for. Defaults to None.
        weight_init (OneToOne | None, optional): initializer for weights. Defaults to None.
        bias_init (OneToOne | None, optional): initializer for biases. Defaults to None.
        delay_init (OneToOne | None, optional): initializer for delays. Defaults to None.

    Raises:
        ValueError: step time must be a positive real.
        ValueError: delay, if not none, must be a positive real.
    """
    def __init__(
        self,
        in_shape: tuple[int, ...] | int,
        out_shape: tuple[int, ...] | int,
        step_time: float,
        *,
        synapse: SynapseConstructor,
        batch_size: int = 1,
        bias: bool = False,
        delay: float | None = None,
        weight_init: OneToOne | None = None,
        bias_init: OneToOne | None = None,
        delay_init: OneToOne | None = None,
    ):
        # convert shapes
        try:
            in_shape = (int(in_shape),)
        except TypeError:
            in_shape = tuple(int(s) for s in in_shape)
        try:
            out_shape = (int(out_shape),)
        except TypeError:
            out_shape = tuple(int(s) for s in out_shape)

        input_size = math.prod(in_shape)
        output_size = math.prod(out_shape)

        # check that the step time is valid
        if float(step_time) <= 0:
            raise ValueError(f"step time must be positive, received {float(step_time)}")

        # check that the delay is valid
        if delay is not None and float(delay) <= 0:
            raise ValueError(
                f"delay, if not none, must be positive, received {float(delay)}"
            )

        # call superclass constructor
        Connection.__init__(
            self,
            synapse=synapse(
                input_size,
                float(step_time),
                int(batch_size),
                None if not delay else float(delay),
            ),
            weight=nn.Parameter(
                torch.rand(output_size, input_size), requires_grad=False
            ),
            bias=(
                None
                if not bias
                else nn.Parameter(torch.rand(output_size, 1), requires_grad=False)
            ),
            delay=(
                None
                if not delay
                else nn.Parameter(
                    torch.zeros(output_size, input_size),
                    requires_grad=False,
                )
            ),
        )

        # register extras
        self.register_extra("in_shape", in_shape)
        self.register_extra("out_shape", out_shape)

        # initialize parameters
        if weight_init:
            self.weight = weight_init(self.weight)

        if bias_init and bias:
            self.bias = bias_init(self.bias)

        if delay_init and delay:
            self.delay = delay_init(self.delay)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        r"""Generates connection output from inputs, after passing through the synapse.

        Outputs are determened as the learned linear transformation applied to synaptic
        currents, after new input is applied to the synapse. These are reshaped according
        to the specified output shape.

        Args:
            inputs (torch.Tensor): inputs to the connection.

        Returns:
            torch.Tensor: outputs from the connection.
        """
        if self.delayed:
            _ = self.synapse(ein.rearrange(inputs, "b ... -> b (...)"))
            res = self.synapse.current_at(self.delay)

            if self.bias is not None:
                res = torch.sum(res * self.weight + self.bias, dim=-1)
            else:
                res = torch.sum(res * self.weight, dim=-1)

        else:
            res = self.synapse(ein.rearrange(inputs, "b ... -> b (...)"))
            res = F.linear(res, self.weight, self.bias)

        return res.view(-1, *self.outshape)

    @property
    def inshape(self) -> tuple[int]:
        r"""Shape of inputs to the connection, excluding the batch dimension.

        Returns:
            tuple[int]: shape of inputs to the connection.
        """
        return self.in_shape

    @property
    def outshape(self) -> tuple[int]:
        r"""Shape of outputs from the connection, excluding the batch dimension.

        Returns:
            tuple[int]: shape of outputs from the connection.
        """
        return self.out_shape


class DirectLinear(WeightBiasDelayMixin, Connection):
    r"""Linear one-to-one connection.

    .. math::
        y = x \odot w + b

    Args:
        shape (tuple[int, ...] | int): expected shape of input/output tensor, excluding batch.
        step_time (float): length of a simulation time step, in :math:`\mathrm{ms}`.
        synapse (SynapseConstructor): partial constructor for inner :py:class:`~inferno.neural.Synapse`.
        batch_size (int, optional): size of input batches for simualtion. Defaults to 1.
        bias (bool, optional): if the connection should include learnable additive bias. Defaults to False.
        delay (float | None, optional): length of time the connection should support delays for. Defaults to None.
        weight_init (OneToOne | None, optional): initializer for weights. Defaults to None.
        bias_init (OneToOne | None, optional): initializer for biases. Defaults to None.
        delay_init (OneToOne | None, optional): initializer for delays. Defaults to None.

    Raises:
        ValueError: step time must be a positive real.
        ValueError: delay, if not none, must be a positive real.
    """
    def __init__(
        self,
        shape: tuple[int, ...] | int,
        step_time: float,
        *,
        synapse: SynapseConstructor,
        batch_size: int = 1,
        bias: bool = False,
        delay: float | None = None,
        weight_init: OneToOne | None = None,
        bias_init: OneToOne | None = None,
        delay_init: OneToOne | None = None,
    ):
        # convert shapes
        try:
            shape = (int(shape),)
        except TypeError:
            shape = tuple(int(s) for s in shape)

        size = math.prod(shape)

        # check that the step time is valid
        if float(step_time) <= 0:
            raise ValueError(
                f"step time must be greater than zero, received {float(step_time)}"
            )

        # check that the delay is valid
        if delay is not None and float(delay) <= 0:
            raise ValueError(
                f"delay, if not none, must be positive, received {float(delay)}"
            )

        # call superclass constructor
        Connection.__init__(
            self,
            synapse=synapse(
                size,
                float(step_time),
                int(batch_size),
                None if not delay else float(delay),
            ),
            weight=nn.Parameter(torch.rand(size), requires_grad=False),
            bias=(
                None
                if not bias
                else nn.Parameter(torch.rand(size), requires_grad=False)
            ),
            delay=(
                None
                if not delay
                else nn.Parameter(
                    torch.zeros(size),
                    requires_grad=False,
                )
            ),
        )

        # register extras
        self.register_extra("shape", shape)

        # initialize parameters
        if weight_init:
            self.weight = weight_init(self.weight)

        if bias_init and bias:
            self.bias = bias_init(self.bias)

        if delay_init and delay:
            self.delay = delay_init(self.delay)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        r"""Generates connection output from inputs, after passing through the synapse.

        Outputs are determened as the learned linear transformation applied to synaptic
        currents, after new input is applied to the synapse. These are reshaped according
        to the specified output shape.

        Args:
            inputs (torch.Tensor): inputs to the connection.

        Returns:
            torch.Tensor: outputs from the connection.
        """
        if self.delayed:
            _ = self.synapse(ein.rearrange(inputs, "b ... -> b (...)"))
            res = ein.rearrange(
                self.synapse.current_at(self.delay.view(-1, 1)), "b 1 n -> b n"
            )

            if self.bias is not None:
                res = res * self.weight + self.bias
            else:
                res = res * self.weight

        else:
            res = self.synapse(ein.rearrange(inputs, "b ... -> b (...)"))

            if self.bias is not None:
                res = res * self.weight + self.bias
            else:
                res = res * self.weight

        return res.view(-1, *self.outshape)

    @property
    def inshape(self) -> tuple[int]:
        r"""Shape of inputs to the connection, excluding the batch dimension.

        Returns:
            tuple[int]: shape of inputs to the connection.
        """
        return self.shape

    @property
    def outshape(self) -> tuple[int]:
        r"""Shape of outputs from the connection, excluding the batch dimension.

        Returns:
            tuple[int]: shape of outputs from the connection.
        """
        return self.shape


class LateralLinear(WeightBiasDelayMixin, Connection):
    r"""Linear all-to-"all but one" connection.

    .. math::
        y = x \left(W^\intercal \odot (1 - I\right)) + b

    Args:
        shape (tuple[int, ...] | int): expected shape of input/output tensor, excluding batch.
        step_time (float): length of a simulation time step, in :math:`\mathrm{ms}`.
        synapse (SynapseConstructor): partial constructor for inner :py:class:`~inferno.neural.Synapse`.
        batch_size (int, optional): size of input batches for simualtion. Defaults to 1.
        bias (bool, optional): if the connection should include learnable additive bias. Defaults to False.
        delay (float | None, optional): length of time the connection should support delays for. Defaults to None.
        weight_init (OneToOne | None, optional): initializer for weights. Defaults to None.
        bias_init (OneToOne | None, optional): initializer for biases. Defaults to None.
        delay_init (OneToOne | None, optional): initializer for delays. Defaults to None.

    Raises:
        ValueError: step time must be a positive real.
        ValueError: delay, if not none, must be a positive real.
    """
    def __init__(
        self,
        shape: tuple[int, ...] | int,
        step_time: float,
        *,
        synapse: SynapseConstructor,
        batch_size: int = 1,
        bias: bool = False,
        delay: float | None = None,
        weight_init: OneToOne | None = None,
        bias_init: OneToOne | None = None,
        delay_init: OneToOne | None = None,
    ):
        # convert shapes
        try:
            shape = (int(shape),)
        except TypeError:
            shape = tuple(int(s) for s in shape)

        size = math.prod(shape)

        # check that the step time is valid
        if float(step_time) <= 0:
            raise ValueError(f"step time must be positive, received {float(step_time)}")

        # check that the delay is valid
        if delay is not None and float(delay) <= 0:
            raise ValueError(
                f"delay, if not none, must be positive, received {float(delay)}"
            )

        # call superclass constructor
        Connection.__init__(
            self,
            synapse=synapse(
                size,
                float(step_time),
                int(batch_size),
                None if not delay else float(delay),
            ),
            weight=nn.Parameter(
                torch.rand(size, size) * (1 - torch.eye(size)), requires_grad=False
            ),
            bias=(
                None
                if not bias
                else nn.Parameter(torch.rand(size, 1), requires_grad=False)
            ),
            delay=(
                None
                if not delay
                else nn.Parameter(
                    torch.zeros(size, size),
                    requires_grad=False,
                )
            ),
        )

        # register buffer
        self.register_buffer("_mask", 1 - torch.eye(size))

        # register extras
        self.register_extra("shape", shape)

        # initialize parameters
        if weight_init:
            self.weight = weight_init(self.weight)

        if bias_init and bias:
            self.bias = bias_init(self.bias)

        if delay_init and delay:
            self.delay = delay_init(self.delay)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        r"""Generates connection output from inputs, after passing through the synapse.

        Outputs are determened as the learned linear transformation applied to synaptic
        currents, after new input is applied to the synapse. These are reshaped according
        to the specified output shape.

        Args:
            inputs (torch.Tensor): inputs to the connection.

        Returns:
            torch.Tensor: outputs from the connection.
        """
        if self.delayed:
            _ = self.synapse(ein.rearrange(inputs, "b ... -> b (...)"))
            res = self.synapse.current_at(self.delay * self._mask)

            if self.bias is not None:
                res = torch.sum(res * self.weight * self._mask + self.bias, dim=-1)
            else:
                res = torch.sum(res * self.weight * self._mask, dim=-1)

        else:
            res = self.synapse(ein.rearrange(inputs, "b ... -> b (...)"))
            res = F.linear(res, self.weight * self._mask, self.bias)

        return res.view(-1, *self.outshape)

    @property
    def inshape(self) -> tuple[int]:
        r"""Shape of inputs to the connection, excluding the batch dimension.

        Returns:
            tuple[int]: shape of inputs to the connection.
        """
        return self.shape

    @property
    def outshape(self) -> tuple[int]:
        r"""Shape of outputs from the connection, excluding the batch dimension.

        Returns:
            tuple[int]: shape of outputs from the connection.
        """
        return self.shape
