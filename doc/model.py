from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DocuLink:
    guideName: str
    link: str
    responsible: str
    accountable: str
    consulted: str
    informed: str
    pdfPath: Optional[Path] = None
    mdPath: Optional[Path] = None
    brdPath: Optional[Path] = None
    improveCounter: int = 0

    def __str__(self):
        return f"Guide Document Name: {self.guideName}\nLink: {self.link}\nResponsible: {self.responsible}\nAccountable: {self.accountable}\nConsulted: {self.consulted}\nInformed: {self.informed}\nPDF Path: {self.pdfPath}\nMD Path: {self.mdPath}\nBRD Path: {self.brdPath}"
