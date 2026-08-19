import os
import tempfile

import ebi
import pm4py
from pm4py.objects.conversion.log import converter as log_converter
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


def precision_alignments_ebi(log, model: ProcessTree) -> float:
    event_log = log_converter.apply(
        log,
        variant=log_converter.Variants.TO_EVENT_LOG,
    )

    model_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".ptml",
            delete=False,
        ) as tmp:
            model_path = tmp.name

        pm4py.write_ptml(
            model,
            model_path,
        )

        with open(
            model_path,
            "r",
            encoding="utf-8",
        ) as file:
            model_string = file.read()

        alignments = ebi.conformance_non_stochastic_alignments(
            event_log,
            model_string,
        )

        precision = ebi.conformance_non_stochastic_escaping_edges_precision(
            alignments,
            model_string,
        )

        if isinstance(precision, (list, tuple)):
            precision = precision[0]

        return float(precision)

    finally:
        if model_path is not None and os.path.exists(model_path):
            os.remove(model_path)


if __name__ == "__main__":
    log_path = "./evaluation/data/SEPSIS.xes"

    log = pm4py.read_xes(log_path)

    dataframe = log_converter.apply(
        log,
        variant=log_converter.Variants.TO_DATA_FRAME,
    )

    model = pm4py.discover_process_tree_inductive(
        dataframe,
    )

    print("Model:")
    print(model)

    precision = precision_alignments_ebi(
        dataframe,
        model,
    )

    print("Ebi precision:")
    print(precision)
    print("Precision, alignments:")
    print(precision_alignment_tree(dataframe, model))
