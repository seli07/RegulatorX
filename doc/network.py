import hashlib
import os
import re
from pathlib import Path
from typing import Tuple, Union

import requests as req

from .model import DocuLink


def checkDownloadable(doc: DocuLink):
    docHeader = req.head(doc.link, allow_redirects=True)
    linkType = docHeader.headers["content-type"].lower()
    if "text" in linkType or "html" in linkType:
        return False
    return True


def getFileNameFromHeader(header: Union[str, None]) -> str:
    if header:
        name = re.findall("filename=(.+)", header)
        if len(name) == 0 or len(name[0]) == 0:
            return ""
        else:
            return name[0]
    else:
        return ""


def getFileNameFromLink(url: str) -> str:
    matches = re.findall(r"^.*\/(.+\..+)$", url)
    return matches[0] if len(matches) != 0 else ""


def getFileName(response: req.Response) -> str:
    # fn = getFileNameFromHeader(response.headers.get("content-deposition"))
    fn = ""
    if fn.lower().strip() == "":
        fn = getFileNameFromLink(response.url)
    return fn


def downloadFile(doc: DocuLink) -> Tuple[DocuLink, bool]:
    response = req.get(doc.link, allow_redirects=True)
    fileName = getFileName(response)
    if doc.pdfPath:
        origMD5 = getFileMD5(doc.pdfPath)
        # print(f"Old MD5 for {doc.pdfPath}: {origMD5}")
    else:
        origMD5 = ""
    # print(f"Saving {doc.guideName} as {fileName}")
    savePath = Path("./data/rawPDFs") / fileName
    open(Path("./data/rawPDFs") / fileName, "wb").write(response.content)
    if os.path.exists(savePath):
        doc.pdfPath = Path(savePath)
    return doc, not (origMD5 == getFileMD5(savePath))


def getFileMD5(file: Path) -> str:
    return hashlib.md5(open(file, "rb").read()).hexdigest()
