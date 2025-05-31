import random
from itertools import cycle
from sys import stdout as terminal
from threading import Thread
from time import sleep

spinners = [
    [
        "[       ]",
        "[=      ]",
        "[==     ]",
        "[===    ]",
        "[ ===   ]",
        "[  ===  ]",
        "[   === ]",
        "[    ===]",
        "[     ==]",
        "[      =]",
        "[       ]",
    ],
    [
        "[●      ]",
        "[ ●     ]",
        "[  ●    ]",
        "[   ●   ]",
        "[    ●  ]",
        "[     ● ]",
        "[      ●]",
    ],
]


class LoadingAnim(object):
    def __init__(
        self, animStepDelay=0.1, loadingMessage="Loading", doneMessage="Done!"
    ):
        self.loadingMessage = loadingMessage
        self.doneMessage = doneMessage
        self.done = True
        self.CURSOR_UP_ONE = "\x1b[1A"
        self.ERASE_LINE = "\x1b[2K"

    def start(self, loadingMessage=None, doneMessage=None):
        l = loadingMessage if loadingMessage else self.loadingMessage
        d = doneMessage if doneMessage else self.doneMessage
        if self.done:
            self.done = False
            t = Thread(target=self.animate, args=[l, d])
            t.start()

    def stop(self):
        self.done = True
        sleep(0.25)

    def animate(self, loadingMessage, doneMessage):
        global done
        for c in cycle(random.choice(spinners)):
            if self.done:
                print(self.ERASE_LINE + self.CURSOR_UP_ONE)
                break
            terminal.write(f"\r{loadingMessage} " + c)
            terminal.flush()
            sleep(0.1)
        terminal.write(f"{doneMessage}")
        terminal.flush()
