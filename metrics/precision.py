import os
import subprocess
import tempfile

import pm4py
import powl
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


def precision_alignments_ebi_rust(
    log,
    model: ProcessTree,
    binary="./ebi_precision/target/release/ebi_precision",
):
    net, _, _ = (
        pm4py.convert_to_petri_net(model) if isinstance(model, ProcessTree) else model
    )
    powl_model = powl.convert_from_workflow_net(net)

    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "log.xes")
        model_path = os.path.join(tmp_dir, "model.powl")
        sali_path = os.path.join(tmp_dir, "alignments.sali")
        precision_path = os.path.join(tmp_dir, "precision.txt")

        pm4py.write_xes(
            log,
            log_path,
        )

        powl.write_powl_json(
            powl_model,
            model_path,
        )

        subprocess.run(
            [
                binary,
                log_path,
                model_path,
                sali_path,
                precision_path,
            ],
            check=True,
        )

        with open(
            precision_path,
            "r",
            encoding="utf-8",
        ) as file:
            precision = file.read().strip()

        if "/" in precision:
            numerator, denominator = precision.split("/", 1)
            return float(numerator) / float(denominator)

        return float(precision)


def precision_alignments_ebi_rust_sm(
    log,
    model,
    binary="./ebi_precision/target/release/ebi_precision",
):
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "log.xes")
        sali_path = os.path.join(tmp_dir, "alignments.sali")
        precision_path = os.path.join(tmp_dir, "precision.txt")

        pm4py.write_xes(log, log_path)

        if isinstance(model, ProcessTree):
            model_path = os.path.join(tmp_dir, "model.ptml")
            pm4py.write_ptml(model, model_path)

        else:
            # Expect (net, initial_marking, final_marking)
            net, im, fm = model
            model_path = os.path.join(tmp_dir, "model.pnml")

            pm4py.write_pnml(
                net,
                im,
                fm,
                model_path,
            )

        subprocess.run(
            [
                binary,
                log_path,
                model_path,
                sali_path,
                precision_path,
            ],
            check=True,
        )

        with open(
            precision_path,
            "r",
            encoding="utf-8",
        ) as file:
            precision = file.read().strip()

        if "/" in precision:
            numerator, denominator = precision.split("/", 1)
            return float(numerator) / float(denominator)

        return float(precision)


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

    precision = precision_alignments_ebi_rust(
        dataframe,
        model,
    )

    print("Ebi precision:")
    print(precision)
    print("Precision, alignments:")
    print(precision_alignment_tree(dataframe, model))
