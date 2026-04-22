import pm4py


# Metrics for simplicity/complexity
def control_flow_complexity(net):
    transitions = len(net.transitions)
    places_complexity = 0
    for place in net.places:
        for transition in net.transitions:
            if place in transition.in_arcs:
                places_complexity += 1
    return transitions + places_complexity


def complexity_size(net):
    return len(net.transitions) + len(net.places)


def simplicity_cardaso(net, *args):
    return pm4py.algo.evaluation.simplicity.algorithm.apply(
        net, variant=pm4py.algo.evaluation.simplicity.variants.extended_cardoso
    )


def simplicity_cyclomatic(net, im, *args):
    return pm4py.algo.evaluation.simplicity.algorithm.apply(
        net, im, variant=pm4py.algo.evaluation.simplicity.variants.extended_cyclomatic
    )


def simplicity_arc_degree(net, im, *args):
    return pm4py.algo.evaluation.simplicity.algorithm.apply(
        net, im, variant=pm4py.algo.evaluation.simplicity.variants.arc_degree
    )
