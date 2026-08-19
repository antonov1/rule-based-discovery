import ebi
import pm4py
from pm4py.objects.petri_net.obj import Marking, PetriNet
from pm4py.objects.process_tree.obj import ProcessTree


def precision_alignment_tree(log, model: ProcessTree):
    net, im, fm = pm4py.convert_to_petri_net(model)
    return precision_alignment_pnet(log, net, im, fm)


def precision_alignment_pnet(log, net: PetriNet, im: Marking, fm: Marking):
    return pm4py.conformance.precision_alignments(log, net, im, fm)


def precision_token_based_tree(log, model: ProcessTree):
    net, im, fm = pm4py.convert_to_petri_net(model)
    return precision_token_based_pnet(log, net, im, fm)


def precision_token_based_pnet(log, net: PetriNet, im: Marking, fm: Marking):
    return pm4py.conformance.precision_token_based_replay(log, net, im, fm)


def precision_alignments_ebi(log, model: ProcessTree):
    try:
        alignments = ebi.conformance_non_stochastic_alignments(
            log,
            model,
        )

        precision = ebi.conformance_non_stochastic_escaping_edges_precision(
            alignments,
            model,
        )

        # Ebi exact fraction:
        # [floating-point approximation, numerator, denominator]
        if isinstance(precision, (list, tuple)):
            precision = precision[0]

        return float(precision)

    except Exception as e:
        print(f"The exception is: {e}")
        input("Press Enter to continue...")
        return None
