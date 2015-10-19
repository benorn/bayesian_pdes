import numpy as np
import pairwise
from sympy_helpers import sympy_function, two_arg_applier


def generate_op_cache(operators, operators_bar, k, symbols, mode):
    ret = {
        tuple(): functionize(k, symbols, mode=mode)
    }
    for op in operators:
        if op not in ret:
            ret[op] = functionize(op(k), symbols, mode=mode)
    for op in operators_bar:
        if op not in ret:
            ret[op] = functionize(op(k), symbols, mode=mode)
    # combinations
    for op in operators:
        for op_bar in operators_bar:
            # don't do anything if already there
            if (op, op_bar) in ret:
                pass
            # exploit symmetry
            elif (op_bar, op) in ret:
                ret[(op, op_bar)] = ret[(op_bar, op)]
            # no choice!!
            else:
                ret[(op, op_bar)] = functionize(op(op_bar(k)), symbols, mode=mode)
    return ret


def collocate(operators, operators_bar, k, symbols, observations, op_cache=None):
    """
    Construct a collocation approximation to the system of operators supplied.
    :param operators: List of operators operators (as functions which operate on sympy expressions)
    :param operators_bar: List of operators working on the second argument of the kernel.
    :param k: The kernel itself, as a sympy expression
    :param symbols: Sympy symbols for the kernel. Note that thanks to sympy being a bit peculiar we can't easily use
    vector operations here - instead each component must be supplied separately if we are working in a higher-dimensional
    space.
    In this event, the sympy symbols should be grouped into sub-lists according to which vector they belong to,
    eg. [[x_1, x_2], [y_1, y_2]]
    :param observations: List of observations. Size should match the size of the list of operators.
    It should be a list of tuples, [(obs locations, obs values)], where obs locations has m rows and d columns and
    values has m rows and 1 column. Here m is the number of points observed and d is the dimension of each point.
    :return: A function which, when given a set of test points, returns the posterior mean and covariance at those
    points.
    """

    if op_cache is None:
        op_cache = generate_op_cache(operators, operators_bar, k, symbols)
    k_eval = op_cache[()]

    points = [p for p, _ in observations]

    L = apply_1d(operators, points, op_cache)
    Lbar = apply_1d(operators_bar, points, op_cache)

    LLbar = calc_LLbar(operators, operators_bar, observations, op_cache)
    LLbar_inv = np.linalg.inv(LLbar)

    # and the observation vector...
    g = np.concatenate([val for _, val in observations])
    #print np.c_[np.concatenate([o for o, _ in observations]), g]

    # finally return the posterior
    def __posterior(test_points):
        Lbar_test = Lbar(test_points)
        L_test = L(test_points)

        mu = Lbar_test.T.dot(LLbar_inv).dot(g)
        Sigma = k_eval(test_points, test_points) - Lbar_test.T.dot(LLbar_inv).dot(L_test)

        return mu, Sigma

    return __posterior


# for now we only support sympy, maybe later support Theano?
# nest inside a function which will apply the result pairwise
def functionize(fun, symbols, mode='compile', apply_factory=two_arg_applier):
    sympy_fun = sympy_function(fun, symbols, mode=mode, apply_factory=apply_factory)

    def __ret_function(a, b):
        return pairwise.apply(sympy_fun, a, b)

    return __ret_function


# build the 1D operators
def apply_1d(operators, observations, op_cache):
    """
    Given an array of operators and a sympy expression to apply them to, plus the symbols,
    return a lambda function which can be used to evaluate the operator applied to the function in a grid.
    :param operators: The operators
    :param k: The sympy expression
    :param symbols: Arguments of the sympy expression
    :param observations: points to constitute the rows.
    :return:
    """
    assert len(operators) == len(observations), "Number of operators must match number of observations"
    tmp = []
    for op in operators:
        functioned = op_cache[op]
        tmp.append(functioned)
    return lambda x: np.hstack([f(x, obs) for f, obs in zip(tmp, observations)]).T


def calc_LLbar(operators, operators_bar, observations, op_cache):
    # and build the 2D matrix
    LLbar = []

    for op, obs_1 in zip(operators, observations):
        tmp = []
        for op_bar, obs_2 in zip(operators_bar, observations):
            points_1, _ = obs_1
            points_2, _ = obs_2

            fun_op = op_cache[(op, op_bar)]

            applied = fun_op(points_1, points_2)
            tmp.append(applied)
        LLbar.append(np.hstack(tmp))

    return np.vstack(LLbar)
