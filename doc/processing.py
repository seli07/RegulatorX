import json
import os
import re
from pathlib import Path

import numpy as np

# from markitdown import MarkItDown
import pymupdf4llm
from docling.document_converter import DocumentConverter

from doc.network import getFileNameFromLink

from .model import DocuLink

PAGEBREAK = '<div style="page-break-after: always;"></div>'


def DLinkFromNumpy(array: np.ndarray):
    link = DocuLink(
        guideName=array[0],
        link=array[1],
        responsible=array[2],
        accountable=array[3],
        consulted=array[4],
        informed=array[5],
    )
    fileStem = Path(getFileNameFromLink(link.link)).stem
    if fileStem:
        pdfFile = Path("./data/rawPDFs") / (fileStem + ".pdf")
        mdFile = Path("./data/convertedMDs") / (fileStem + ".pymu.md")
        brdFile = Path("./data/brdMDs") / (fileStem + ".pymu.brd.md")
        if os.path.exists(mdFile):
            link.mdPath = mdFile
        if os.path.exists(brdFile):
            link.brdPath = brdFile
        if os.path.exists(pdfFile):
            link.pdfPath = pdfFile
    return link


def convertToMarkdown(doc: DocuLink):
    # md = MarkItDown()
    if doc.pdfPath:
        # data = md.convert_local(doc.pdfPath)
        data = pymupdf4llm.to_markdown(doc.pdfPath)
        # print(data.text_content)
        mdPath = Path("./data/convertedMDs") / f"{doc.pdfPath.stem}.pymu.md"
        saveMarkdown(data, mdPath)
        doc.mdPath = mdPath
    return doc


def convertToMarkdownDocLing(doc: DocuLink):
    # md = MarkItDown()
    md = DocumentConverter()
    if doc.pdfPath:
        data = md.convert(doc.pdfPath)
        # data = pymupdf4llm.to_markdown(doc.pdfPath)
        # print(data.text_content)
        mdPath = Path("./data/convertedMDs") / f"{doc.pdfPath.stem}.docling.md"
        saveMarkdown(data.document.export_to_markdown(), mdPath)
        doc.mdPath = mdPath
    return doc


def saveMarkdown(data: str, path: Path):
    with open(path, "w") as f:
        f.write(data)


def formatTextAsMarkdown(text: str) -> str:
    """
    Format text in Microsoft Markdown style.

    Args:
        text: Raw text to format

    Returns:
        Formatted text in Microsoft Markdown
    """
    if not text:
        return "# No Content\n\n*No text content was available for formatting.*"

    # Old notation compatibility
    formattedText = text.replace("\r\n", "\n")

    # Split into lines
    lines = formattedText.split("\n")
    formattedLines = []

    inTable = False
    tableHeaderRow = False

    for line in lines:
        originalLine = line
        line = line.strip()

        # Skip empty lines
        if not line:
            formattedLines.append("")
            continue

        # Detect tables
        if "|" in line and len(line.split("|")) >= 3:
            if not inTable:
                inTable = True
                tableHeaderRow = True
                formattedLines.append(line)
                columnCount = len(line.split("|")) - 1
                formattedLines.append("|" + "|".join(["---"] * columnCount) + "|")
            else:
                if tableHeaderRow:
                    tableHeaderRow = False
                formattedLines.append(line)
        else:
            inTable = False

            # Identify section headers (all caps, short lines)
            if line.isupper() and len(line) < 100 and len(line) > 3:
                formattedLines.append(f"### {line}")
            # Identify subsection headers
            elif re.match(r"^[\d\.]+\s+[A-Z]", line) and len(line) < 100:
                formattedLines.append(f"#### {line}")
            else:
                formattedLines.append(originalLine)

    # Join lines into single string
    formattedText = "\n".join(formattedLines)

    # Add horizontal rules for better visual separation
    formattedText = re.sub(r"\n{3,}", "\n\n---\n\n", formattedText)

    return formattedText


def getJsonDict(data: str):
    data = data.removeprefix("```json")
    data = data.removesuffix("```")
    return json.loads(data)
