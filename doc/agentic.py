import json
from pathlib import Path
from typing import Dict, Optional

from google import genai

from doc import loadingBar
from doc.debugPrint import Log, genDebugFunction
from doc.processing import getJsonDict

from .model import DocuLink

printf = genDebugFunction()


def critic(brd: str, cg: str, apiToken: str):
    prompt = f"""Given a companion guide(cg) and its business require document(brd), critique the brd and provide a review of the document.
    Also provide a score between 0 to 1 which denotes the quality and similarity of the converted BRD.
    Focus on improving the clarity, completeness and regulatory compliance.
    Identify any gaps in requirement or missing references.
    Be very specific and concise about the changes instead of general comments.
    Return the response in json format only.
    Provide the score in the `score` key.
    Provide the critiquing statements in the key `critic` in a single string.

    CG: {cg}


    BRD: {brd}

"""

    resp = callAgent(prompt, apiToken)
    if resp:
        return getJsonDict(resp)
    return {}


# def improve(doc: DocuLink, apiToken: Optional[str]):
#     if doc.mdPath:
#         cg = open(doc.mdPath, "r").read()
#     else:
#         raise ValueError("CG Markdown File Not Found")

#     if doc.brdPath:
#         brd = open(doc.brdPath, "r").read()
#     else:
#         raise ValueError("Base BRD Not Found")

#     feedback = critic(brd, cg, apiToken)
#     newBRD = improveBRD(brd, cg, feedback, apiToken)
#     newBRD = newBRD.removeprefix("```markdown")
#     newBRD = newBRD.removesuffix("```")
#     with open(doc.brdPath, "w") as f:
#         f.write(newBRD)
#     doc.improveCounter += 1
#     print(f"{doc.guideName} improved {doc.improveCounter} times")
#     return doc


def agenticImprove(doc: DocuLink, apiToken: str, scoreThreshold=0.85, maxItrs=10):
    proc = loadingBar.LoadingAnim(doneMessage="", loadingMessage="Improving")
    proc.start("Improving BRD")
    if doc.mdPath:
        cg = open(doc.mdPath, "r").read()
    else:
        proc.stop()
        raise ValueError("CG Markdown File Not Found")

    if doc.brdPath:
        brd = open(doc.brdPath, "r").read()
    else:
        proc.stop()
        raise ValueError("Base BRD Not Found")
    currentScore = 0
    itr = 0
    errItrs = 0
    while (currentScore < scoreThreshold) and ((itr + errItrs) < maxItrs):
        proc.start()
        itr += 1
        try:
            feedback = critic(brd, cg, apiToken)
            if "score" not in feedback:
                # print(feedback.keys())
                raise TypeError("Score not found in reply.")
            if "critic" not in feedback:
                print("No critic provided, finalizing document.")
                break
        except json.decoder.JSONDecodeError as e:
            proc.stop()
            printf("Didnt receive proper json critic from Agent, retrying...", Log.ERR)
            printf("*" * 50, Log.ERR)
            print(e)
            printf("*" * 50, Log.ERR)
            errItrs += 1
            itr -= 1
            if errItrs >= (maxItrs // 2):
                proc.stop()
                printf("Failed too many times, skipping improving document.", Log.ERR)
                return doc
            continue
        except TypeError:
            errItrs += 1
            itr -= 1
            if errItrs >= (maxItrs // 2):
                proc.stop()
                printf(
                    "Missed keys too many times, skipping improving doucment.", Log.ERR
                )
            continue
        currentScore = feedback["score"]
        critics = feedback["critic"]
        newBRD = improveBRD(brd, cg, critics, apiToken)
        newBRD = newBRD.removeprefix("```markdown")
        newBRD = newBRD.removesuffix("```")
        doc.improveCounter += 1
        proc.stop()
        printf(
            "Improvement Itr: {}, Current Score: {}".format(
                doc.improveCounter, currentScore
            ),
            Log.INF,
        )
    with open(doc.brdPath, "w") as f:
        f.write(newBRD)
    printf(f"{doc.guideName} improved {doc.improveCounter} times", Log.SUC)
    return doc


def improveBRD(brd: str, cg: str, feedback: str, apiToken: str) -> str:
    prompt = f"""
    Given a companion guide(CG), the business require document(BRD) and the a critic feedback of the BRD, improve the BRD based on the feedback and CG as reference and return the BRD.
    Dont perform drastic changes. Make sure the quality of the output doesnt deteriorate.
    Only provide the improved BRD markdown content and nothing else.

    CG: {cg}

    BRD: {brd}

    feedback on BRD: {feedback}
    """
    return callAgent(prompt, apiToken)


def convertToBRD(doc: DocuLink, apiToken: Optional[str]):
    proc = loadingBar.LoadingAnim()
    proc.start(loadingMessage="Conterting to BRD")
    if apiToken is None:
        proc.stop()
        raise ValueError("Empty api key")
    if doc.mdPath:
        pass
    else:
        proc.stop()
        raise FileNotFoundError(doc.mdPath)
    mdData = open(doc.mdPath).read()
    prompt = f"""
            {mdData} \nConsider the above content as a companion guide, provide the business requirement document in markdown format.
            Make sure to include the business requirements in table format, each with unique IDs.
            Only provide the markdown content and nothing else"""

    brdData = callAgent(prompt, apiToken)
    if brdData is None:
        proc.stop()
        raise RuntimeError("No content receievd from api")
    brdData = brdData.removeprefix("```markdown")
    brdData = brdData.removesuffix("```")
    outputPath = Path("./data/brdMDs") / f"{doc.mdPath.stem}.brd.md"
    with open(outputPath, "w") as f:
        f.write(brdData)
    doc.brdPath = outputPath
    proc.stop()
    return doc


def getDiffPoints(oldDoc: str, newDoc: str, apiToken: str) -> Dict:
    oldDocData = oldDoc
    newDocData = newDoc

    prompt = f"""
    Below provided are the old and the new versions of a Business Requirement Document.
    Identify and list the key differences found in the new version.
    Reply in json format.
    Include the "count" key, which holds the count of change suggestions, and the "changes" key which holds a list of strings, each denoting a suggestion.

    Old BRD: {oldDocData}

    New BRD: {newDocData}
    """

    # client = genai.Client(api_key=apiToken)
    # response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    diffData = callAgent(prompt, apiToken)
    if diffData == "":
        raise RuntimeError("No content receievd from api")
    try:
        jsonDiff = getJsonDict(diffData)
        return jsonDiff

    except json.decoder.JSONDecodeError:
        print("Error getting proper difference information from agent")
        return {"count": 0}


def callAgent(prompt: str, apiKey: str, model: str = "gemini-2.0-flash") -> str:
    client = genai.Client(api_key=apiKey)
    resp = client.models.generate_content(model=model, contents=prompt).text
    if resp:
        return resp
    else:
        ""
