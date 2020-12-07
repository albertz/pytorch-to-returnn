Make [PyTorch](https://pytorch.org/) code
runnable within [RETURNN](https://github.com/rwth-i6/returnn)
(on TensorFlow).
This provides some wrappers (and maybe some magic) to do that.


# `torch` drop-in replacement for RETURNN

The idea:
```
import torch

class Model(torch.nn.Module):
 ...
```
Would be changed to:
```
from pytorch_to_returnn import torch as torch_returnn

class Model(torch_returnn.nn.Module):
 ...
```
And this can be used directly in RETURNN.

This would convert the model to a RETURNN model.
[Example constructed RETURNN net dict](https://gist.github.com/albertz/01264cfbd2dfd73a19c1e2ac40bdb16b),
created from
[this PyTorch code](https://github.com/albertz/import-parallel-wavegan/blob/main/pytorch_to_returnn.py).

## Why

From PyTorch perspective:

- RETURNN will keep track of the meaning of tensor axes.
I.e. it knows about the batch axis,
and any spatial axes (width/height or time),
including their sequence lengths.
(This goes far beyond just named axes.)
This can be used to verify whether the operations are on the right axes
and to detect potential bugs.

- RETURNN can do further optimizations
and might make the model run faster.
(If this is not the case, likely there is some bug,
or non-optimal implementation on RETURNN side,
which we can improve.)

From RETURNN/TF perspective:

- This can serve as a new way to define your RETURNN networks (TF networks),
which might be simpler to use than the existing way.

- We can reuse PyTorch code, and even trained models,
within RETURNN,
and combine it easily with other RETURNN models.

- We might find non-optimal or buggy implementations in RETURNN
(e.g. when there is some module which runs better/faster in PyTorch)
and can improve upon them (the corresponding RETURNN layer).

## How does this work

On a high level, RETURNN layers mostly corresponds to PyTorch modules.
So all PyTorch modules are mapped directly or indirectly to RETURNN layers.
The same is done for all functions in `functional`.

All RETURNN layers have further meta information about tensors,
esp their axes/dimensions,
and they might reorder axes when this is more efficient.
We keep track of the axis mapping.

See the [documentation of the `pytorch_to_returnn.torch` package](pytorch_to_returnn/torch)
for details about how this works,
and what can be done with it.
Obviously, this is incomplete.
For some status of what is not supported currently,
see [the unsupported document](Unsupported.md).
Otherwise, when you hit some `Module`
or `functional` function, or Tensor function
which is not implemented,
it just means that no-one has implemented it yet.

Somewhat related is also the `torch.fx` module.


# Import wrapper

We also support to transform external PyTorch code
on-the-fly
(without the need to rewrite the code;
it translates the code on AST level in the way above on-the-fly).
I.e. it basically replaces
`import torch` by `from pytorch_to_returnn import torch`
-- that's all it does. 

This is via our [generic Python import wrapper `pytorch_to_returnn.import_wrapper`](pytorch_to_returnn/import_wrapper).

Example for [Parallel WaveGAN](https://github.com/kan-bayashi/ParallelWaveGAN):
```
from pytorch_to_returnn.import_wrapper import wrapped_import_torch_returnn
from pytorch_to_returnn.naming import Naming
from returnn.tf.util.data import Data

torch = wrapped_import_torch_returnn("torch")
wrapped_import_torch_returnn("parallel_wavegan")
pwg_models = wrapped_import_torch_returnn("parallel_wavegan.models")
pwg_layers = wrapped_import_torch_returnn("parallel_wavegan.layers")

with Naming.make_instance() as naming:
    inputs = torch.from_numpy(inputs)  # shape (Batch,Channel,Feature), e.g. (1,80,80)
    x = naming.register_input(
        inputs, Data("data", shape=(80, None), feature_dim_axis=1, time_dim_axis=2))
    assert isinstance(x, Data)

    # Initialize PWG
    pwg_config = yaml.load(open(args.pwg_config), Loader=yaml.Loader)
    generator = pwg_models.MelGANGenerator(**pwg_config['generator_params'])
    generator.load_state_dict(
        torch.load(args.pwg_checkpoint, map_location="cpu")["model"]["generator"])
    generator.remove_weight_norm()
    pwg_model = generator.eval()
    pwg_pqmf = pwg_layers.PQMF(pwg_config["generator_params"]["out_channels"])
    
    outputs = pwg_pqmf.synthesis(pwg_model(inputs))

    outputs = naming.register_output(outputs)
    y = outputs.returnn_data
    assert isinstance(y, Data)

```


# Model converter

For the process of converting a model from PyTorch to RETURNN,
including a PyTorch model checkpoint,
we provide some utilities to automate this,
and verify whether all outputs match.
This is in [`pytorch_to_returnn.converter`](pytorch_to_returnn/converter).

Example for [Parallel WaveGAN](https://github.com/kan-bayashi/ParallelWaveGAN):
```
def model_func(wrapped_import, inputs: torch.Tensor):
    if typing.TYPE_CHECKING or not wrapped_import:
        import torch
        from parallel_wavegan import models as pwg_models
        from parallel_wavegan import layers as pwg_layers

    else:
        torch = wrapped_import("torch")
        wrapped_import("parallel_wavegan")
        pwg_models = wrapped_import("parallel_wavegan.models")
        pwg_layers = wrapped_import("parallel_wavegan.layers")

    # Initialize PWG
    pwg_config = yaml.load(open(args.pwg_config), Loader=yaml.Loader)
    generator = pwg_models.MelGANGenerator(**pwg_config['generator_params'])
    generator.load_state_dict(
        torch.load(args.pwg_checkpoint, map_location="cpu")["model"]["generator"])
    generator.remove_weight_norm()
    pwg_model = generator.eval()
    pwg_pqmf = pwg_layers.PQMF(pwg_config["generator_params"]["out_channels"])

    return pwg_pqmf.synthesis(pwg_model(inputs))


feature_data = numpy.load(args.features)  # shape (Batch,Channel,Time) (1,80,80)

from pytorch_to_returnn.converter import verify_torch_and_convert_to_returnn
verify_torch_and_convert_to_returnn(model_func, inputs=feature_data)
```

This will automatically do the conversion,
i.e. create a RETURNN model,
including the [RETURNN net dict](https://gist.github.com/albertz/01264cfbd2dfd73a19c1e2ac40bdb16b)
and TF checkpoint file,
and do verification on several steps of all the outputs.


# Direct use in RETURNN

```
from pytorch_to_returnn import torch as torch_returnn

class MyTorchModel(torch_returnn.nn.Module):
  ...

my_torch_model = MyTorchModel() 

extern_data = {...}  # as usual

# RETURNN network dict
network = {
"prenet": my_torch_model.as_returnn_layer_dict(extern_data["data"]),

# Other RETURNN layers
...
}
```

Or:

```
from pytorch_to_returnn import torch as torch_returnn

class MyTorchModel(torch_returnn.nn.Module):
  ...

my_torch_model = MyTorchModel() 

extern_data = {...}  # as usual

# RETURNN network dict
network = my_torch_model.as_returnn_net_dict(extern_data["data"])
```
