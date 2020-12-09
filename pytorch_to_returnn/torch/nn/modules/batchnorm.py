
from __future__ import annotations
import tensorflow as tf
import math
from typing import Optional, Dict, Any
from .module import Module
from .utils import _single, _pair, _triple, _reverse_repeat_tuple, _ntuple
from ..common_types import _scalar_or_tuple_any_t, _size_1_t, _size_2_t, _size_3_t
from ..functional import zeros, ones, tensor
from ...tensor import Tensor
from ..parameter import Parameter
from .. import init


class _NormBase(Module):
  """Common base of _InstanceNorm and _BatchNorm"""
  _version = 2

  def __init__(
      self,
      num_features: int,
      eps: float = 1e-5,
      momentum: float = 0.1,
      affine: bool = True,
      track_running_stats: bool = True
  ) -> None:
    super(_NormBase, self).__init__()
    self.num_features = num_features
    self.eps = eps
    self.momentum = momentum
    self.affine = affine
    self.track_running_stats = track_running_stats
    if self.affine:
      self.weight = Parameter(Tensor(num_features))
      self.bias = Parameter(Tensor(num_features))
    else:
      self.register_parameter('weight', None)
      self.register_parameter('bias', None)
    if self.track_running_stats:
      self.register_buffer('running_mean', zeros(num_features))
      self.register_buffer('running_var', ones(num_features))
      self.register_buffer('num_batches_tracked', tensor(0, dtype="int64"))
    else:
      self.register_parameter('running_mean', None)
      self.register_parameter('running_var', None)
      self.register_parameter('num_batches_tracked', None)
    self.reset_parameters()

  def reset_running_stats(self) -> None:
    if self.track_running_stats:
      self.running_mean.zero_()
      self.running_var.fill_(1)
      self.num_batches_tracked.zero_()

  def reset_parameters(self) -> None:
    self.reset_running_stats()
    if self.affine:
      init.ones_(self.weight)
      init.zeros_(self.bias)

  def _check_input_dim(self, input):
    raise NotImplementedError

  def extra_repr(self):
    return '{num_features}, eps={eps}, momentum={momentum}, affine={affine}, ' \
           'track_running_stats={track_running_stats}'.format(**self.__dict__)

  def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict,
                            missing_keys, unexpected_keys, error_msgs):
    version = local_metadata.get('version', None)

    if (version is None or version < 2) and self.track_running_stats:
      # at version 2: added num_batches_tracked buffer
      #               this should have a default value of 0
      num_batches_tracked_key = prefix + 'num_batches_tracked'
      if num_batches_tracked_key not in state_dict:
        state_dict[num_batches_tracked_key] = tensor(0, dtype="int64")

    super(_NormBase, self)._load_from_state_dict(
      state_dict, prefix, local_metadata, strict,
      missing_keys, unexpected_keys, error_msgs)


class _BatchNorm(_NormBase):
  def __init__(self, num_features, eps=1e-5, momentum=0.1, affine=True, track_running_stats=True):
    super(_BatchNorm, self).__init__(num_features, eps, momentum, affine, track_running_stats)

  def create_returnn_layer_dict(self, input: Tensor) -> Dict[str, Any]:
    return {
      "class": "batch_norm", "from": self._get_input_layer_name(input),
      "momentum": self.momentum, "epsilon": self.eps}


class BatchNorm1d(_BatchNorm):
  pass


__all__ = [
  key for (key, value) in sorted(globals().items())
  if not key.startswith("_")
  and getattr(value, "__module__", "") == __name__]