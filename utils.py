import os


def createDataStorage():
    os.makedirs("./data/rawPDFs", exist_ok=True)
    os.makedirs("./data/convertedMDs", exist_ok=True)
    os.makedirs("./data/brdMDs", exist_ok=True)
    os.makedirs("./data/brdDocs", exist_ok=True)
