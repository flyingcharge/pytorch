from functools import reduce

from ..function import Function, InplaceFunction


class _DimReduceFunction(Function):
    def __init__(self, dim=None):
        super(_DimReduceFunction, self).__init__()
        self.dim = dim

    def forward(self, input):
        self.input_size = input.size().tolist()
        fn = getattr(input, self.fn_name)
        if self.dim is None:
            return input.new((fn(),))
        else:
            return fn(self.dim)


class Sum(_DimReduceFunction):
    fn_name = 'sum'

    def backward(self, grad_output):
        if self.dim is None:
            return grad_output.new(*self.input_size).fill_(grad_output[0])
        else:
            repeats = [1 for _ in self.input_size]
            repeats[self.dim] = self.input_size[self.dim]
            return grad_output.repeatTensor(*repeats),


class Mean(_DimReduceFunction):
    fn_name = 'mean'

    def backward(self, grad_output):
        if self.dim is None:
            grad_input_val = grad_output[0]
            grad_input_val /= reduce(lambda x,y: x * y, self.input_size, 1)
            return grad_output.new(*self.input_size).fill_(grad_input_val)
        else:
            repeats = [1 for _ in self.input_size]
            dim_size = self.input_size[self.dim]
            repeats[self.dim] = dim_size
            return grad_output.repeatTensor(*repeats).div_(dim_size)


class _SelectionFunction(Function):
    has_all_reduce = True

    def __init__(self, dim=None, return_indices=False):
        super(_SelectionFunction, self).__init__()
        self.dim = dim
        self.return_indices = return_indices
        assert not self.return_indices or dim is not None

    def forward(self, input):
        fn = getattr(input, type(self).__name__.lower())
        self.input_size = input.size().tolist()
        if self.dim is None and self.has_all_reduce:
            max_value = fn()
            self.max_index = input.eq(max_value).nonzero()[0]
            return input.new((max_value,))
        else:
            dim = self.dim or input.dim()-1
            output, indices = fn(dim)
            if self.return_indices:
                self.save_for_backward(indices)
                self.mark_non_differentiable(indices)
                return output, indices
            else:
                self.indices = indices
                return output

    def backward(self, grad_output):
        grad_input = grad_output.new(*self.input_size).zero_()
        if self.dim is None and self.has_all_reduce:
            (grad_input.view(-1))[self.max_index] = grad_output[0]
        else:
            if self.return_indices:
                indices, = self.saved_tensors
            else:
                indices = self.indices
            dim = self.dim or grad_output.dim() - 1
            grad_input.scatter_(dim, indices, grad_output)
        return grad_input


class Max(_SelectionFunction):
    pass


class Min(_SelectionFunction):
    pass


class Mode(_SelectionFunction):
    has_all_reduce = False


class Median(_SelectionFunction):
    has_all_reduce = False


# TODO: dist
# TODO: norm
# TODO: prod
# TODO: renorm
# TODO: std
# TODO: var
