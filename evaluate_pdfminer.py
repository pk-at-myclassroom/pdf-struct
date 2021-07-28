import copy
import json
import os

import click

from pdf_struct.core import transition_labels
from pdf_struct.loader.pdf import load_from_directory
from pdf_struct.core.structure_evaluation import evaluate_labels
from pdf_struct.core.predictor import ListAction
from pdf_struct.core.utils import pairwise


@click.command()
@click.argument('raw-dir', type=click.Path(exists=True))
@click.argument('anno-dir', type=click.Path(exists=True))
def main(raw_dir: str, anno_dir: str):
    print(f'Loading annotations from {anno_dir}')
    annos = transition_labels.load_annos(anno_dir)

    print('Loading and extracting features from raw files')
    documents = load_from_directory(raw_dir, annos)
    documents_pred = []
    for document in documents:
        d = copy.deepcopy(document)
        labels = []
        for tb1, tb2 in pairwise(d.text_blocks):
            labels.append(
                ListAction.CONTINUOUS if len(tb1.blocks & tb2.blocks) > 0 else ListAction.SAME_LEVEL
            )
        pointers = [None] * len(labels)
        labels.append(ListAction.UP)
        pointers.append(-1)
        d.labels = labels
        d.pointers = pointers
        documents_pred.append(d)

    print(json.dumps(evaluate_labels(documents, documents_pred), indent=2))


if __name__ == '__main__':
    main()
