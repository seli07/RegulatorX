import enum
from datetime import datetime


class bcolors:
    # bcolors class taken from https://svn.blender.org/svnroot/bf-blender/trunk/blender/build_files/scons/tools/bcolors.py
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"


class Log(enum.Enum):
    SUC = 0
    INF = 1
    WRN = 2
    ERR = 3


def genDebugFunction(
    printTime: bool = False,
    printDelta: bool = False,
    deltaResolution: int = 3,
    saveToFile=None,
    # *args,
    # **kwargs,
):
    global _printerDelta
    global fileWriter
    _printerDelta = datetime.now()
    enableWriter = False
    if saveToFile is None:
        enableWriter = False
    elif isinstance(saveToFile, str):
        fileWriter = open(saveToFile, mode="a+")
        enableWriter = True
    elif hasattr(saveToFile, "flush"):
        fileWriter = saveToFile
        enableWriter = True

    def debug(
        comment,
        level: Log = Log.INF,
        printTime=printTime,
        printDelta=printDelta,
        deltaResolution=deltaResolution,
        enableWriter=enableWriter,
        *args,
        **kwargs,
    ):
        if printTime:
            tm = datetime.now().isoformat(" ")
        else:
            tm = ""

        if printDelta:
            global _printerDelta
            delta = (
                "+"
                + f"{round((datetime.now() - _printerDelta).total_seconds(),deltaResolution):.{deltaResolution}f}"
                + "s "
            )
            _printerDelta = datetime.now()
        else:
            delta = ""

        if printDelta and printTime:
            joiner = ": "
        elif printTime:
            joiner = " "
        else:
            joiner = ""

        if enableWriter:
            global fileWriter
            fileWriter.write(f"{tm}{joiner}{delta}{comment}\n")
            fileWriter.flush()

        if level == Log.INF:
            print(
                f"{bcolors.OKBLUE}{tm}{joiner}{delta}[i]",
                comment,
                bcolors.ENDC,
                *args,
                **kwargs,
            )
        elif level == Log.WRN:
            print(
                f"{bcolors.WARNING}{tm}{joiner}{delta}[!]",
                comment,
                bcolors.ENDC,
                *args,
                **kwargs,
            )
        elif level == Log.ERR:
            print(
                f"{bcolors.FAIL}{tm}{joiner}{delta}[x]",
                comment,
                bcolors.ENDC,
                *args,
                **kwargs,
            )
        elif level == Log.SUC:
            print(
                f"{bcolors.OKGREEN}{tm}{joiner}{delta}[✓]",
                comment,
                bcolors.ENDC,
                *args,
                **kwargs,
            )

    return debug


if __name__ == "__main__":
    debug = genDebugFunction()
    debug("info")
    debug("warn", Log.WRN)
    debug("error", Log.ERR)
    debug("success", Log.SUC)
