import glob
import os
from typing import List

import tqdm

from pdf_struct.text.features import PlainTextFeatureExtractor
from pdf_struct.text.parser import TextLine
from pdf_struct.transition_labels import DocumentWithFeatures, ListAction, \
    AnnoListType
from pdf_struct.utils import get_filename


class TextDocumentLoadingError(ValueError):
    pass


class TextDocumentWithFeatures(DocumentWithFeatures):
    @classmethod
    def load(cls, path: str, labels: List[ListAction], pointers: List[int], dummy_feats: bool=False):
        with open(path, 'r') as fin:
            text_lines = TextLine.from_lines([line for line in fin])
        if len(text_lines) == 0:
            raise TextDocumentLoadingError('No text boxes found.')
        if len(labels) != len(text_lines):
            raise TextDocumentLoadingError('Number of rows does not match labels.')

        text_boxes, labels, pointers = cls._filter_text_blocks(text_lines, labels, pointers)
        texts = [tb.text for tb in text_boxes]

        feature_extractor, feats, pointer_feats = cls._extract_features(
            PlainTextFeatureExtractor, text_boxes, labels, pointers, dummy_feats)

        return cls(path, feats, texts, labels, pointers, pointer_feats,
                   feature_extractor, text_boxes)


def load_texts(base_dir: str, annos: AnnoListType, dummy_feats: bool=False) -> List[TextDocumentWithFeatures]:
    paths = glob.glob(os.path.join(base_dir, '*.txt'))
    # filter first for tqdm to work properly
    paths = [path for path in paths if get_filename(path) in annos]
    documents = []
    for path in tqdm.tqdm(paths):
        anno = annos[get_filename(path)]
        try:
            documents.append(TextDocumentWithFeatures.load(
                path, [a[0] for a in anno], [a[1] for a in anno], dummy_feats=dummy_feats))
        except TextDocumentLoadingError as e:
            print(f'Loading "{path}" failed. {e}')
    return documents
