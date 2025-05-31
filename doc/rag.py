import json
import os
from hashlib import md5
from pathlib import Path

import chromadb
import google.genai as genai
from chromadb import Documents, EmbeddingFunction, Embeddings
from dotenv import load_dotenv
from tqdm.auto import tqdm

from doc.debugPrint import Log, genDebugFunction
from doc.processing import getJsonDict

load_dotenv()

printf = genDebugFunction()


class DocuRAG(object):
    def __init__(self, savePath: Path, dbName: str):
        self.savePath = savePath
        self.dbName = dbName
        self.apiKey = os.environ["GEMINI_API_KEY"]
        self.fileMap = {}
        self.createDB()
        # self.loadDB()
        self.docIDCounter = 0

    def saveFileMap(self):
        with open(self.savePath / "fileMap.json", "w") as f:
            f.write(json.dumps(self.fileMap))

    def createDB(self):
        try:
            self.loadDB()
        except chromadb.errors.NotFoundError:
            printf("Creating new Database", Log.WRN)
            chromaClient = chromadb.PersistentClient(path=str(self.savePath))
            self.db = chromaClient.create_collection(
                name=self.dbName, embedding_function=GeminiEmbeddingFunction()
            )
        except Exception as e:
            raise e

    def loadDB(self):
        chromaClient = chromadb.PersistentClient(path=str(self.savePath))
        self.db = chromaClient.get_collection(
            name=self.dbName, embedding_function=GeminiEmbeddingFunction()
        )
        printf("Loading Existing Database", Log.INF)
        if os.path.exists(self.savePath / "fileMap.json"):
            with open(self.savePath / "fileMap.json", "r") as f:
                self.fileMap = json.loads(f.read())

    def addDocsToDB(self, documentPath: Path, debug=False):
        if debug:
            print(f"Adding {documentPath} to RAG DataBase")
        documentContent = open(documentPath).read()
        documentContent = f"File Contents of {str(documentPath)}:\n" + documentContent
        docuHash = md5(documentContent.encode()).hexdigest()
        if str(documentPath) in self.fileMap:
            oldFileInfo = self.fileMap[str(documentPath)]
            ## check for updates and update if necessary. else add to db with new id.
            if docuHash == oldFileInfo[1]:
                if debug:
                    print(f"{str(documentPath)} didnt change")
                pass  # Same file, pass adding
            else:
                self.db.update(
                    oldFileInfo[0], documents=documentContent
                )  # updated file, update the db
                self.fileMap[str(documentPath)] = (oldFileInfo[0], docuHash)
                self.saveFileMap()
                if debug:
                    print(f"Updated {str(documentPath)}")
        else:
            self.db.add(documents=documentContent, ids=str(self.docIDCounter))
            self.fileMap[str(documentPath)] = (self.docIDCounter, docuHash)
            self.saveFileMap()

    def addCodeBase(self, projectRoot: Path):
        files = list(projectRoot.rglob("[!_]*.py"))
        bar = tqdm(files, leave=False)
        for i in bar:
            bar.set_postfix_str(str(i))
            self.addDocsToDB(i, False)

    def formatPrompt(self, query: str, ragMatch: str):
        escaped = ragMatch.replace("'", "").replace('"', "").replace("\n", " ")
        prompt = f"""You are a helpful and informative bot that answers questions using text from the reference passage included below. \
      QUESTION: '{query}'
      PASSAGE: '{escaped}'

      ANSWER:
      """
        return prompt

    def callPrompt(self, prompt):
        client = genai.Client(api_key=self.apiKey)
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        if response.text:
            return response.text
        else:
            return ""

    def getRelatedText(self, query, resultCount=3):
        res = self.db.query(query_texts=[query], n_results=resultCount)["documents"][0][
            0
        ]
        return res

    def generate(self, query: str):
        relevantText = self.getRelatedText(query)
        prompt = self.formatPrompt(query=query, ragMatch=relevantText)
        return self.callPrompt(prompt)

    def getCodeSuggestion(self, change: str):
        prompt = f"""
        For the given suggestion, provide the relevant modified code: {change}.
        Reply in json format, with the mandatory key "count", denoting the number of code changes for the given suggestion.
        If no changes are necessary, reply in json format with count equal to 0.
        If there are any changes, format each suggestion as a json document as below, and return a list of such suggesion document under the key "changes":
            1. path of the file to change to the key "filename"
            2. short explanation about the change to the key "description"
            3. the code snippet to change to the key "oldCode"
            4. the code snippet modified as per the provided change to the key "newCode"


        make sure the json keys are properly present.
        """
        relevantText = self.getRelatedText(change)
        prompt = self.formatPrompt(query=prompt, ragMatch=relevantText)
        return getJsonDict(self.callPrompt(prompt))


class GeminiEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError(
                "Gemini API Key not provided. Please provide GEMINI_API_KEY as an environment variable"
            )
        client = genai.Client(api_key=gemini_api_key)
        model = "models/gemini-embedding-exp-03-07"
        emb = client.models.embed_content(
            model=model,
            contents=[input],
        ).embeddings
        return [i.values for i in emb]


# if __name__ == "__main__":
#     a = DocuRAG(savePath=Path("./data"), dbName="data")
#     a.loadDB()

#     data = open(
#         "/home/fader/Codes/SE/documan/referenceFiles/ky_validation_code/kentucky_medicaid_837i_processor.py"
#     ).read()
#     a.addDocsToDB([data])
#     # a.addDocsToDB(["asrarstarst"])

#     prompt = "retrieve the code which generates handles Processing the 2300 HI Segment for the “Other Procedure Information. Only provide the code and nothing else"
#     print(a.generate(prompt))
