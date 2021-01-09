from typing import NamedTuple, Generator, Tuple, List, Set
import uuid
from functools import reduce
import operator

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from pdf_struct.preprocessing import preprocess_text
from pdf_struct.transition_labels import TextBlock


class TextBox(TextBlock):
    def __init__(self, text: str, bbox: Tuple[float, float, float, float], page: int, blocks: Set[str]):
        super(TextBox, self).__init__(text)
        # bbox is [x_left, y_bottom, x_right, y_top] in points with
        # left bottom being [0, 0, 0, 0]
        self.bbox: Tuple[float, float, float, float] = bbox
        self.page: int = page
        self.blocks: Set[str] = blocks


def parse_pdf(fs) -> Generator[TextBox, None, None]:
    doc = PDFDocument(PDFParser(fs))
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for page_idx, page in enumerate(PDFPage.create_pages(doc)):
         interpreter.process_page(page)
         layout = device.get_result()
         yield from parse_layout(layout, page_idx + 1, None)


def parse_layout(layout, page: int, block: str):
    for lt_obj in layout:
        if isinstance(lt_obj, LTTextLine):
            text = preprocess_text(lt_obj.get_text().strip('\n'))
            if block is None:
                block = uuid.uuid4().hex
            if len(text.strip()) > 0:
                yield TextBox(text, lt_obj.bbox, page, {block})
        elif isinstance(lt_obj, LTTextBox):
            block = uuid.uuid4().hex
            yield from parse_layout(lt_obj, page, block)
        elif isinstance(lt_obj, LTFigure):
            pass


def merge_continuous_lines(text_boxes: List[TextBox], threshold=0.5):
    ex = 4   # ex is about 4pt
    if len(text_boxes) <= 1:
        return text_boxes
    text_boxes = sorted(text_boxes, key=lambda b: (b.page, -b.bbox[1], b.bbox[0]))
    merged_text_boxes = []
    i = 0
    while i < (len(text_boxes) - 1):
        tbi = text_boxes[i]
        # aggregate text boxes in same line then merge
        same_line_boxes = [tbi]
        for j in range(i + 1, len(text_boxes)):
            tbj = text_boxes[j]
            if tbi.page != tbj.page:
                break
            # text_boxes[j]'s y_bottom is always lower than text_boxes[i]'s
            span = max(tbi.bbox[3], tbj.bbox[3]) - tbj.bbox[1]
            overlap = min(tbi.bbox[3], tbj.bbox[3]) - tbi.bbox[1]
            if overlap / span > threshold:
                same_line_boxes.append(tbj)
                continue
            else:
                # stop scanning for same line for efficiency
                break
        if len(same_line_boxes) > 1:
            # sort left to right
            same_line_boxes = sorted(same_line_boxes, key=lambda b: b.bbox[0])
            text = same_line_boxes[0].text.strip('\n')
            bbox = same_line_boxes[0].bbox
            for tbk in same_line_boxes[1:]:
                spaces = max(tbk.bbox[0] - bbox[2], 0)
                text += int(spaces // ex) * ' '
                text += tbk.text.strip('\n')
                bbox = [
                    bbox[0],
                    min(bbox[1], tbk.bbox[1]),
                    max(bbox[2], tbk.bbox[2]),
                    max(bbox[3], tbk.bbox[3])
                ]
            blocks = reduce(operator.or_, (b.blocks for b in same_line_boxes))
            merged_text_boxes.append(TextBox(text, bbox, tbi.page, blocks))
        else:
            merged_text_boxes.append(tbi)
        i = j
    # if len(same_line_boxes) == 1 in last loop, text_boxes[-1] will be missing
    if len(same_line_boxes) == 1:
        merged_text_boxes.append(text_boxes[-1])
    return merged_text_boxes


def get_margins(clusters, n_pages):
    # I don't think header/footer rows exceed 3 respectively
    min_occurances = n_pages * (3 + 3) + 1
    for c in clusters:
        if len(c) >= min_occurances:
            return c
    return clusters[0]
