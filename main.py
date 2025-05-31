import os
from hashlib import md5
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from dotenv import load_dotenv

from doc import loadingBar
from doc.agentic import agenticImprove, convertToBRD, getDiffPoints
from doc.debugPrint import Log, genDebugFunction
from doc.model import DocuLink
from doc.network import checkDownloadable, downloadFile
from doc.processing import DLinkFromNumpy, convertToMarkdown
from doc.rag import DocuRAG
from utils import createDataStorage

load_dotenv()

printf = genDebugFunction()


class DocuFlow(object):
    def __init__(self, documentCSV: Path, codeBase: Path):
        printf("  Initializing DocuMan  ".center(50, "v"), Log.WRN)
        createDataStorage()
        self.docList = pd.read_csv(documentCSV)
        self.docs: Dict[str, DocuLink] = {}

        for doc in self.docList.to_numpy():
            doc = DLinkFromNumpy(doc)
            self.processDocLink(doc, True)
            print()

        printf("Adding Code to RAG DB".center(50, "-"), Log.WRN)
        self.ragAgent = DocuRAG(savePath=Path("./data/ragData"), dbName="differ")
        self.ragAgent.addCodeBase(codeBase)
        printf("Done Preparing RAG".center(50, "-"), Log.SUC)
        print()
        printf("  Done Initializing DocuMan  ".center(50, "^"), Log.SUC)
        print()

    def processDocLink(self, newDoc: DocuLink, download=False) -> Tuple[bool, str, str]:
        print()
        printf(f"  Processing {newDoc.guideName} Guide  ".center(50, "*"), Log.WRN)
        proc = loadingBar.LoadingAnim(loadingMessage="Processing", doneMessage="")
        proc.start()
        oldMD = None
        updated = False
        if newDoc.guideName in self.docs:
            proc.stop()
            printf(f"Updating {newDoc.guideName}", Log.INF)
            proc.start(loadingMessage="Updating", doneMessage="")
            oldDoc = self.docs[newDoc.guideName]
            oldPDFHash = md5(open(oldDoc.pdfPath, "rb").read()).hexdigest()
            newPDFHash = md5(open(newDoc.pdfPath, "rb").read()).hexdigest()
            if oldPDFHash == newPDFHash:
                proc.stop()
                printf("PDF Contents didnt change, skipping update", Log.WRN)
                printf("*" * 50, Log.WRN)
                print()
                return (False, "", "")
            newDoc.accountable = oldDoc.accountable
            newDoc.consulted = oldDoc.consulted
            newDoc.informed = oldDoc.informed
            newDoc.responsible = oldDoc.responsible
            newDoc.link = newDoc.link
            newDoc.improveCounter = 0
            if os.path.exists(str(oldDoc.mdPath)):
                oldMD = open(str(oldDoc.mdPath)).read()
                updated = True
        if download:
            proc.start(loadingMessage="Downloading")
            isDownloadable = checkDownloadable(newDoc)
            if isDownloadable:
                newDoc, updated = downloadFile(newDoc)
            else:
                proc.stop()
                printf(f"{newDoc.guideName} not downloadable, skipping.", Log.ERR)
                printf("*" * 50, Log.ERR)
                print()
                return (False, "", "")
        self.docs[newDoc.guideName] = newDoc

        if updated or (newDoc.mdPath is None):
            proc.stop()
            printf(f"Converting {newDoc.guideName} to Markdown")
            proc.start(loadingMessage="Converting to MD")
            newDoc = convertToMarkdown(newDoc)
        else:
            proc.stop()
            printf("MD Already Exists", Log.WRN)
            proc.start()
        if updated or (newDoc.brdPath is None):
            proc.stop()
            printf(f"Converting {newDoc.guideName} to BRD")
            # proc.start("Creating BRD using Agents")
            newDoc = convertToBRD(newDoc, os.getenv("GEMINI_API_KEY"))
            newDoc = agenticImprove(newDoc, os.getenv("GEMINI_API_KEY"))
        else:
            proc.stop()
            printf("BRD Already Exists", Log.WRN)
            proc.start()

        self.docs[newDoc.guideName] = newDoc
        if oldMD:
            newMD = open(str(newDoc.mdPath)).read()
            if md5(oldMD.encode()).hexdigest() != md5(newMD.encode()).hexdigest():
                proc.stop()
                printf(
                    "  Done Processing, Update Available  ".center(50, "*") + "\n",
                    Log.SUC,
                )
                return (True, oldMD, newMD)
            else:
                proc.stop()
                printf(
                    "  Done Processing, Doc Didn't Change  ".center(50, "*") + "\n",
                    Log.SUC,
                )
                return (False, "", "")
        else:
            proc.stop()
            printf("  Done Processing, Saved New Doc  ".center(50, "*") + "\n", Log.SUC)
            return (False, "", "")

    def loop(self):
        try:
            while True:
                newCG = input("Enter Updated CG Name(or q to quit): ")
                if newCG.lower() == "q":
                    return 0
                newDoc = input(
                    "Enter location of new Doc: "
                )  # currently takes offline location of pdf. later to be changed to a url.
                newDoc = Path(newDoc)
                if newCG not in self.docs:
                    printf("CG Not in standard list", Log.ERR)
                    continue
                oldDoc = self.docs[newCG]
                if os.path.exists(newDoc):
                    newDoc = DocuLink(
                        guideName=newCG,
                        link=oldDoc.link,
                        responsible="",
                        accountable="",
                        consulted="",
                        informed="",
                        pdfPath=newDoc,
                    )
                else:
                    printf(
                        "Provided document doesnt exist, please check the path\n",
                        Log.ERR,
                    )
                    continue
                mdUpdated, oldMD, newMD = self.processDocLink(newDoc)

                if mdUpdated:
                    printf("Code Update Stage".center(50, "-"), Log.WRN)
                    printf("Document has updates, querying for code changes", Log.INF)
                    proc = loadingBar.LoadingAnim(
                        doneMessage="", loadingMessage="Fetching Count"
                    )
                    proc.start()
                    diffs = getDiffPoints(oldMD, newMD, os.getenv("GEMINI_API_KEY"))
                    proc.stop()
                    if diffs["count"] > 0:
                        printf(
                            f"Need {diffs['count']} code changes to code base.", Log.INF
                        )
                        proc = loadingBar.LoadingAnim(
                            doneMessage="",
                            loadingMessage="Generating Next Suggestion",
                        )

                        i = 0
                        for ch in diffs["changes"]:
                            # print("Generating Next Code Suggestion")
                            proc.start()
                            codeSugg = self.ragAgent.getCodeSuggestion(ch)
                            proc.stop()
                            # print(codeSugg["changes"])
                            if "changes" not in codeSugg:
                                printf("Error parsing following change", Log.ERR)
                                print(ch)
                                print()
                                continue
                            for c in codeSugg["changes"]:
                                i += 1
                                print()
                                printf(f"Change {i}".center(50, "."), Log.INF)
                                printf("File to change:")
                                print(c["filename"])
                                printf("Description:")
                                print(c["description"])
                                printf("Old Code:")
                                print(c["oldCode"])
                                printf("New Code:")
                                print(c["newCode"])
                                printf("." * 50)
                                print()

                            ## Print suggested change
                            input("Change the code as suggested above and press enter")
                            print("\x1b[1A\x1b[2K\x1b[1A")
                            proc.start(loadingMessage="Updating RAG", doneMessage="")
                            proc.start()
                            for f in codeSugg["changes"]:
                                self.ragAgent.addDocsToDB(f["filename"])
                            proc.stop()
                        printf("End of change suggestions".center(50, "-"), Log.SUC)
                    else:
                        printf(" Code need not be changed ".center(50, "-"), Log.WRN)
                # else:
                #     printf(
                #         " Document didnt change, no updates required ".center(50, "-"),
                #         Log.WRN,
                #     )
                print("\n")

        except KeyboardInterrupt:
            print("\nReceived Exit Signal, stopping DocuMan")
            return 0


if __name__ == "__main__":
    flow = DocuFlow(codeBase=Path("codeBase"), documentCSV=Path("docList.csv"))
    flow.loop()
