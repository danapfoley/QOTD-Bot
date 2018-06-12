import time
import json
from tempfile import NamedTemporaryFile
import shutil
from typing import List, Dict, Optional

POLLS_FILE_NAME = "polls.json"


class PollQuestion:
    def __init__(self, userID, pID, pollQuestionText, options = {}, responses = {}):
        self.userID: str = userID
        self.pID: str = pID
        self.pollQuestionText: str = pollQuestionText
        self.options: Dict[str, str] = options
        self.responses: Dict[str, str] = responses
        self.published: bool = False
        self.justPublished: bool = False
        self.results: Dict[str, int] = {}
        
    def cleanUpResponse(self, response: str):
        response = response.lower().strip()
        removeChars = ["'", "’", "-"]

        for char in removeChars:
            response = response.replace(char, "")

        return response

    def submitResponse(self, userID: str, inputResponse: str) -> bool:
        if inputResponse in self.options.keys():
            self.responses[userID] = inputResponse
            return True
        return False

    def prettyPrint(self) -> str:
        output = "(" + self.pID + "): " + self.pollQuestionText + "\n"

        for option in sorted(self.options.keys()):
            output += "    (" + option + "): " + self.options[option] + "\n"

        return output

    def calculateResults(self):
        for key in self.options.keys():
            self.results[key] = 0
        for vote in self.responses.values():
            if vote in self.results:
                self.results[vote] += 1
            else:
                self.results[vote] = 1 

    def displayResults(self) -> str:
        self.calculateResults()

        output = "(" + self.pID + "): " + self.pollQuestionText + "\n"

        for option in self.results:
            output += "    " + str(self.results[option]) + " - " + self.options[option] + "\n"

        output = "\n".join(sorted(output.split("\n"), reverse = True))
        return output

    def publish(self) -> bool:
        if self.published:
            return False
        else:
            self.published = True
            self.justPublished = True
            return True

class PollKeeper:
    def __init__(self):
        self.pollQuestionList = []
        self.loadPollsFromFile()

    def loadPollsFromFile(self):
        with open(POLLS_FILE_NAME) as pFile:
            d = json.load(pFile)
            for pJson in d["polls"]:
                p = PollQuestion(pJson["userID"], pJson["pID"], pJson["pollQuestionText"], pJson["options"], pJson["responses"])
                p.published = pJson["published"]
                p.justPublished = pJson["justPublished"]

                self.pollQuestionList.append(p)

    def writePollsToFile(self):
        pollsJson = {"polls" : []}

        for p in self.pollQuestionList:
            pollsJson["polls"].append(vars(p))

        tempfile = NamedTemporaryFile(delete=False)
        with open(POLLS_FILE_NAME, 'w') as tempfile:
            json.dump(pollsJson, tempfile, indent = 4)

        shutil.move(tempfile.name, POLLS_FILE_NAME)

    def addPoll(self, userID: str, pID: str, pollQuestionText: str, options: dict = {}, responses: dict = {}) -> bool:

        for p in self.pollQuestionList:
            if pID.lower() == p.pID.lower():
                return False
        
        self.pollQuestionList.append(PollQuestion(userID, pID, pollQuestionText, options, responses))

        #save new data
        self.writePollsToFile()
        return True

    def removePoll(self, pID: str, userID: str) -> bool:

        for p in self.pollQuestionList:
            if pID.lower() == p.pID.lower() and (p.userID == userID or userID == "DEV"):
                self.pollQuestionList.remove(p)
                
                #save new data
                self.writePollsToFile()
                return True
        return False

    def getPollByID(self, pID: str) -> Optional[PollQuestion]:
        for p in self.pollQuestionList:
            if pID.lower() == p.pID.lower():
                return p
            
        return None

    def getSubmitterByPID(self, pID):
        p = self.getPollByID(pID)
        if p:
            return p.userID
        else:
            return None

    def submitResponse(self, userID: str, pID: str, inputResponse: str) -> str:
        p = self.getPollByID(pID)
        if p and p.published:
            if p.submitResponse(userID, inputResponse):
                self.writePollsToFile()
                return "ok"
            else:
                return "bad vote"

        return "not found"

    def listPolls(self) -> str:
        output = ""
        for p in self.pollQuestionList:
            if p.published:
                output += p.prettyPrint() + "\n"
        return output

    def listPollsByUser(self, userID: str) -> str:
        output = ""
        for p in self.pollQuestionList:
            if p.userID == userID:
                output += p.prettyPrint() + (" (published)" if p.published else "") + "\n"
        return output

    def expirePoll(self, pID: str, userID: str) -> List[PollQuestion]:
        pollsExpired = []

        if pID != "":
            p = self.getPollByID(pID)
            if p is None:
                return pollsExpired
            if p.userID == userID:
                pollsExpired.append(p)
        else:
            for p in self.pollQuestionList:
                if p.userID == userID:
                    pollsExpired.append(p)

        self.pollQuestionList = [p for p in self.pollQuestionList if p not in pollsExpired]
        pollsExpired = [p.prettyPrintWithAnswer() for p in pollsExpired]
        self.writePollsToFile()

        return pollsExpired

    def publishByID(self, pID: str) -> str:
        p = self.getPollByID(pID)
        if p:
            if p.publish():
                self.writePollsToFile()
                return "published"
            else:
                return "already published"
        else:
            return "notFound"

    def publishAllByUser(self, userID: str):
        for p in self.pollQuestionList:
            if p.userID == userID:
                p.publish()
        self.writePollsToFile()

    def firstTimeDisplay(self) -> str:
        output = ""
        for p in self.pollQuestionList:
            if p.justPublished:
                p.justPublished = False
                output += p.prettyPrint() + "\n\n"
        self.writePollsToFile()
        return output

    def displayResults(self, pID: str) -> Optional[str]:
        p = self.getPollByID(pID)
        if p is None:
            return None
        return p.displayResults()



