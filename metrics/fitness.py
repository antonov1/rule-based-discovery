import pm4py
from metrics.alignments.evaluation import calculate_log_fitness_pta
from pm4py.objects.petri_net.obj import Marking, PetriNet
from pm4py.objects.process_tree.obj import ProcessTree


def fitness_alignment(log, model: ProcessTree):
    return calculate_log_fitness_pta(log, model)


def fitness_alignment_pm4py(log, net, im, fm):
    return pm4py.conformance.fitness_alignments(log, net, im, fm)["log_fitness"]


def fitness_token_based_tree(log, model: ProcessTree):
    net, im, fm = pm4py.convert_to_petri_net(model)
    return fitness_token_based_pnet(log, net, im, fm)


def fitness_token_based_pnet(log, net: PetriNet, im: Marking, fm: Marking):
    return pm4py.conformance.fitness_token_based_replay(log, net, im, fm)["log_fitness"]
