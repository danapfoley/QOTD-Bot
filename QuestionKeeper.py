import time
import json
from tempfile import NamedTemporaryFile
import shutil
from typing import List, Dict, Tuple, Optional

MAX_GUESSES = 3

QUESTIONS_FILE_NAME = "questions.json"
OLD_QUESTIONS_FILE_NAME = "questionsHistory.json"

def splitCategory(qID: str) -> Tuple[str, str]:
    #Splitting the category from qID.
    #Current format is: "Category"qID
    firstInst, lastInst = qID.find('"'), qID.rfind('"')
    category = ""
    if qID.count('"') == 2 and firstInst == 0 and lastInst != (len(qID) - 1):
        category = qID[1:lastInst]
        qID = qID[lastInst+1:]
    return qID, category


class Question:
    def __init__(self, userID, qID, questionText, correctAnswers = [], category = ""):
        self.userID: str = userID
        self.qID: str = qID
        self.questionText: str = questionText
        self.correctAnswers: List[str] = correctAnswers
        self.category: str = category
        self.initTime: float = time.time()
        self.publishTime: float = 0
        self.expireTime: float = 0
        self.published: bool = False
        self.justPublished: bool = False
        self.answeredBy: List[str] = []
        self.guesses: Dict[str, int] = {}

    #We've established rules for which words/characters shouldn't matter in answers.
    #Here is where those get dealt with
    def cleanUpAnswer(self, answer: str) -> str:
        answer = answer.lower().strip()
        words = answer.split(' ')
        removeWords = ["a","an","the","and"]
        removeChars = ["'", "’", "-", ",", ".", "?", "!", "\"", "/", "[", "]", "(", ")", "`", "~"]

        strippedWords = [word for word in words if word not in removeWords]
        answer = ' '.join(strippedWords).strip()

        for char in removeChars:
            answer = answer.replace(char, "")

        return answer

    #This is just for determining answer correctness
    #If we add a feature in the future for requiring a list of items to all be matched,
    #   here is where that should be added.
    def validateAnswer(self, inputAnswer: str) -> bool:
        for correctAnswer in self.correctAnswers:
            match = self.cleanUpAnswer(correctAnswer) == self.cleanUpAnswer(inputAnswer)
            if match:
                return True
        return False

    def checkAnswer(self, userID, inputAnswer: str) -> bool:
        if self.validateAnswer(inputAnswer) and userID not in self.answeredBy:
            self.answeredBy.append(userID)
            return True
        return False

    def addAnswer(self, newAnswer: str):
        self.correctAnswers.append(newAnswer)

    def removeAnswer(self, existingAnswer: str) -> bool:
        if existingAnswer in self.correctAnswers:
            self.correctAnswers.remove(existingAnswer)
            return True
        else:
            return False

    def addUserWhoAnswered(self, userID: str) -> bool:
        if userID in self.answeredBy:
            return False
        self.answeredBy.append(userID)
        return True

    def timeToExpire(self) -> bool:
        return self.published and (time.time() - self.publishTime) > 60 * 60 * 18  #18 hours

    #Display a question with its category and ID in a nicely formatted way
    def prettyPrint(self) -> str:
        output = "" if self.category == "" else (self.category + " ")
        output = output + "(" + self.qID + "): " + self.questionText
        return output

    def prettyPrintWithAnswer(self) -> str:
        return self.prettyPrint() + " : " + (" : ".join(self.correctAnswers) if len(self.correctAnswers) > 0 else "(no answer given)")

    def getAnsweredUsers(self) -> List[str]:
        return self.answeredBy

    def countAnswers(self) -> int:
        return len(self.answeredBy)
    
    def countGuesses(self) -> int:
        return len(self.guesses)

    #There's probably a better way to do this,
    #   but to make sure that only the newly-published questions get displayed,
    #   we have a justPublished flag that is set when publish is called
    #   and unset when QuestionKeeper.firstTimeDisplay is called.
    def publish(self) -> bool:
        if self.published:
            return False
        else:
            self.published = True
            self.justPublished = True
            self.publishTime = time.time()
            return True

class QuestionKeeper:
    def __init__(self):
        self.questionList: List[Question] = []
        self.loadQuestionsFromFile()

    #This only runs on startup to retrieve questions from the persistent file
    def loadQuestionsFromFile(self):
        try:
            file = open(QUESTIONS_FILE_NAME)
            questionsJson = json.load(file)
        except:
            # If not exists, create the file
            questionsJson = {"questions" : []}
            file = open(QUESTIONS_FILE_NAME,"w+")
            json.dump(questionsJson, file, indent = 4)
        file.close()

        with open(QUESTIONS_FILE_NAME) as qFile:
            d = json.load(qFile)
            for qJson in d["questions"]:
                q = Question(qJson["userID"], qJson["qID"], qJson["questionText"], qJson["correctAnswers"], qJson["category"])
                q.initTime = qJson["initTime"]
                q.publishTime = qJson["publishTime"]
                q.published = qJson["published"]
                q.justPublished = qJson["justPublished"]
                q.answeredBy = qJson["answeredBy"]
                q.guesses = qJson["guesses"]

                self.questionList.append(q)
            
    #This is run every time a change occurs to the questionsList data (adding, removing, publishing, guesses being made, etc).
    #   If the bot crashes at any point, we shouldn't lose too much history.
    #   This comes at the cost of frequent write operations, which get costly as the number of questions active at one time grows
    def writeQuestionsToFile(self):
        questionsJson = {"questions" : []}

        for q in self.questionList:
            questionsJson["questions"].append(vars(q))

        tempfile = NamedTemporaryFile(delete=False)
        with open(QUESTIONS_FILE_NAME, 'w') as tempfile:
            json.dump(questionsJson, tempfile, indent = 4)

        shutil.move(tempfile.name, QUESTIONS_FILE_NAME)

    #When questions expire (not get removed), we insert them into the running history of questions in a persistent file
    def writeRemovedQuestionsToFile(self, removedQuestionsList: List[Question]):
        try:
            file = open(OLD_QUESTIONS_FILE_NAME)
            questionsJson = json.load(file)
        except IOError:
            # If not exists, create the file
            questionsJson = {"oldQuestions" : []}
            file = open(OLD_QUESTIONS_FILE_NAME,"w+")
            json.dump(questionsJson, file, indent = 4)
        file.close()
        
        for q in removedQuestionsList:
            questionsJson["oldQuestions"].insert(0, vars(q))

        tempfile = NamedTemporaryFile(delete=False)
        with open(OLD_QUESTIONS_FILE_NAME, 'w') as tempfile:
            json.dump(questionsJson, tempfile, indent = 4)

        shutil.move(tempfile.name, OLD_QUESTIONS_FILE_NAME)

    def addQuestion(self, userID: str, qID: str, questionText: str, correctAnswers: List[str] = []) -> bool:
        qID, category = splitCategory(qID)

        #prevent duplicate IDs
        for q in self.questionList:
            if qID.lower() == q.qID.lower():
                return False
        
        self.questionList.append(Question(userID, qID, questionText, correctAnswers, category))

        #save new data
        self.writeQuestionsToFile()
        return True

    def removeQuestion(self, qID: str, userID: str) -> bool:
        qID, category = splitCategory(qID)

        for q in self.questionList:
            if qID.lower() == q.qID.lower() and (q.userID == userID or userID == "DEV"):
                self.questionList.remove(q)

                # save new data
                self.writeQuestionsToFile()
                return True
        return False

    #Adds a new allowed answer for a question. The userID must be the same as the user who submitted the Q
    def addAnswer(self, userID: str, qID: str, newAnswer: str) -> bool:
        qID, category = splitCategory(qID)

        q = self.getUserQuestionByID(qID, userID)

        if q:
            q.addAnswer(newAnswer)
            self.writeQuestionsToFile()
            return True
        else:
            return False

    #Complementary to addAnswer
    def removeAnswer(self, userID: str, qID: str, existingAnswer: str) -> bool:
        qID, category = splitCategory(qID)

        q = self.getUserQuestionByID(qID, userID)

        if q and q.removeAnswer(existingAnswer):
            self.writeQuestionsToFile()
            return True
        else:
            return False

    def addUserWhoAnswered(self, userID: str, qID: str) -> bool:
        if self.getQuestionByID(qID).addUserWhoAnswered(userID):
            self.writeQuestionsToFile()
            return True
        return False

    def getQuestionByID(self, qID: str) -> Optional[Question]:
        qID, category = splitCategory(qID)

        for q in self.questionList:
            if qID.lower() == q.qID.lower():
                return q

        return None

    #Gets a question only if it was submitted by the user in question, None otherwise
    def getUserQuestionByID(self, qID: str, userID: str) -> Optional[Question]:
        qID, category = splitCategory(qID)
        qID = qID.lower()

        for q in self.questionList:
            if qID == q.qID.lower() and (q.userID == userID or userID == "DEV"):
                return q

        return None

    def getSubmitterByQID(self, qID: str) -> Optional[str]:
        q = self.getQuestionByID(qID)
        if q:
            return q.userID
        else:
            return None

    #Checks for answer correctness when possible, and returns a string based on how it went.
    #There are many possibilities here. If Python had enums, this would be a little bit cleaner
    def checkAnswer(self, userID: str, qID: str, inputAnswer: str) -> str:
        q = self.getQuestionByID(qID)
        if q and q.published:
            #Don't allow guesses after someone has answered already
            if userID in q.answeredBy:
                return "already answered"

            #We want to let users give up on a question,
            #   but thanks to a pesky user demanding that it be possible to have a question
            #   with "I give up" as its answer, we need to make sure we don't interpret a correct answer
            #   as the user giving up
            if inputAnswer.lower() in ["i give up", "give up", "giveup", "igiveup"] and not q.validateAnswer(inputAnswer):
                q.guesses[userID] = MAX_GUESSES
                self.writeQuestionsToFile()
                return "gave up"

            #If we've made it to a point where the user is successfully attempting a guess, increment the counter
            if userID in q.guesses:
                q.guesses[userID] += 1
            else:
                q.guesses[userID] = 1

            #Don't allow guesses beyond the max number allowed
            if q.guesses[userID] >= MAX_GUESSES + 1:
                self.writeQuestionsToFile()
                return "max guesses"
            #Manual question validation is a feature in progress, but we still allow it
            elif q.correctAnswers == []:
                self.writeQuestionsToFile()
                return "needs manual"
            #Finally, we can check if the answer is actually right
            elif q.checkAnswer(userID, inputAnswer):
                self.writeQuestionsToFile()
                return "correct"

            self.writeQuestionsToFile()
            return "incorrect"
        return "not found"

    def listQuestions(self) -> str:
        output = ""
        for q in self.questionList:
            if q.published:
                output += q.prettyPrint() + "\n"
        return output

    #When a user asks to see the questions in a private channel,
    #   we want to show them a bullet point before every question that they could still attempt
    #   Thus:
    #       -They haven't answered it already
    #       -They weren't the one to submit it
    #       -They haven't reached the max number of guesses
    def listQuestionsPrivate(self, userID: str) -> str:
        output = ""
        for q in self.questionList:
            if q.published:
                if userID not in q.answeredBy \
                  and userID != q.userID \
                  and (userID not in q.guesses or q.guesses[userID] < MAX_GUESSES):
                    output += "● "
                output += q.prettyPrint() + "\n"
        return output

    #Same as listQuestionsPrivate, except we just omit the questions that wouldn't have had a bullet point
    def listIncompleteQuestionsPrivate(self, userID: str) -> str:
        output = ""
        for q in self.questionList:
            if q.published \
                    and userID not in q.answeredBy \
                    and (userID not in q.guesses or q.guesses[userID] < MAX_GUESSES):
                output += q.prettyPrint() + "\n"
        return output

    #Called by `my-questions`. Displays a user's questions with answers
    def listQuestionsByUser(self, userID: str) -> str:
        output = ""
        for q in self.questionList:
            if q.userID == userID:
                output += q.prettyPrintWithAnswer() + (" (published)" if q.published else "") + "\n"
        return output

    #Expires all questions over a certain age (right now we're using 18 hours) from a specific user.
    #Returns a list of questions that got expired
    def expireQuestions(self, userID: str) -> List[Question]:
        questionsExpired = []
        for q in self.questionList:
            if q.timeToExpire() and q.userID == userID:
                q.expireTime = time.time()
                questionsExpired.append(q)

        self.questionList = [q for q in self.questionList if q not in questionsExpired]
        
        self.writeQuestionsToFile()
        self.writeRemovedQuestionsToFile(questionsExpired)

        return questionsExpired

    #Publishes one question
    #Should be made user-exclusive in the future
    def publishByID(self, qID: str) -> str:
        q = self.getQuestionByID(qID)
        if q:
            if q.publish():
                self.writeQuestionsToFile()
                return "published"
            else:
                return "already published"
        else:
            return "notFound"

    def publishAllByUser(self, userID: str):
        for q in self.questionList:
            if q.userID == userID:
                q.publish()
        self.writeQuestionsToFile()

    #When a question/questions get published
    def firstTimeDisplay(self) -> str:
        output = ""
        for q in self.questionList:
            if q.justPublished:
                q.justPublished = False
                output += q.prettyPrint() + "\n"
        self.writeQuestionsToFile()
        return output

    #Reads from the questions history file, and returns a string of displayed question that expired less than 24 hours ago
    def getOldQuestionsString(self) -> str:
        try:
            file = open(OLD_QUESTIONS_FILE_NAME)
            oldQuestions = json.load(file)
        except IOError:
            # If not exists, create the file
            oldQuestions = {"oldQuestions" : []}
            file = open(OLD_QUESTIONS_FILE_NAME,"w+")
            json.dump(oldQuestions, file, indent = 4)
        file.close()

        now = time.time()
        elapsedTime = 60 * 60 * 24  #24 hours
        response = ""

        for q in oldQuestions["oldQuestions"]:
            #Questions are inserted at the beginning of the data
            #So it's sorted newer to older
            #Thus if we hit a question older than 24hrs, we can stop searching
            if (now - q["expireTime"]) > elapsedTime:
                break
            response += "" if q["category"] == "" else (q["category"] + " ")
            response += "(" + q["qID"] + "): " + q["questionText"] + " : " + (" : ".join(q["correctAnswers"]) if len(q["correctAnswers"]) > 0 else "(no answer given)")

            response += "\n"

        return response



