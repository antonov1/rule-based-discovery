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


def precision_alignments_ebi(log, model: ProcessTree):
    log_path = None
    model_path = None

    try:
        event_log = log_converter.apply(
            log,
            variant=log_converter.Variants.TO_EVENT_LOG,
        )

        with tempfile.NamedTemporaryFile(
            suffix=".xes.gz",
            delete=False,
        ) as tmp:
            log_path = tmp.name

        pm4py.write_xes(event_log, log_path)

        with tempfile.NamedTemporaryFile(
            suffix=".ptree",
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as tmp:
            model_path = tmp.name
            tmp.write(str(model))

        alignments = ebi.conformance_non_stochastic_alignments(
            log_path,
            model_path,
        )

        precision = ebi.conformance_non_stochastic_escaping_edges_precision(
            alignments,
            model_path,
        )

        if isinstance(precision, (list, tuple)):
            precision = precision[0]

        return float(precision)

    except Exception as e:
        print(f"Ebi precision failed: {e}", flush=True)
        raise

    finally:
        if log_path and os.path.exists(log_path):
            os.remove(log_path)

        if model_path and os.path.exists(model_path):
            os.remove(model_path)
