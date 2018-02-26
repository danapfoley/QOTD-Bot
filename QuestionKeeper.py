import time
import json
from tempfile import NamedTemporaryFile
import shutil

MAX_GUESSES = 3

QUESTIONS_FILE_NAME = "questions.json"

class Question:
    def __init__(self, userID, qID, questionText, correctAnswer = ""):
        self.userID = userID
        self.qID = qID
        self.questionText = questionText
        self.correctAnswer = correctAnswer
        self.initTime = time.time()
        self.publishTime = 0
        self.published = False
        self.justPublished = False
        self.answeredBy = []
        self.guesses = {}
        

    def checkAnswer(self, userID, inputAnswer):
        match = self.correctAnswer.lower() == inputAnswer.lower()
        if match and userID not in self.answeredBy:
            self.answeredBy.append(userID)
        return match

    def timeToExpire(self):
        return (time.time() - self.publishTime) > 86400 #seconds in a day

    def prettyPrint(self):
        return "(" + self.qID + "): " + self.questionText

    def publish(self):
        if self.published:
            return False
        else:
            self.published = True
            self.justPublished = True
            return True

class QuestionKeeper:
    def __init__(self):
        self.questionList = []
        self.loadQuestionsFromFile()

    def loadQuestionsFromFile(self):
        with open(QUESTIONS_FILE_NAME) as qFile:
            d = json.load(qFile)
            print(d)
            for qJson in d["questions"]:
                q = Question(qJson["userID"], qJson["qID"], qJson["questionText"], qJson["correctAnswer"])
                q.initTime = qJson["initTime"]
                q.publishTime = qJson["publishTime"]
                q.published = qJson["published"]
                q.justPublished = qJson["justPublished"]
                q.answeredBy = qJson["answeredBy"]
                q.guesses = qJson["guesses"]

                self.questionList.append(q)
            

    def writeQuestionsToFile(self):
        questionsJson = {"questions" : []}

        for q in self.questionList:
            questionsJson["questions"].append(vars(q))

        tempfile = NamedTemporaryFile(delete=False)
        with open(QUESTIONS_FILE_NAME, 'w') as tempfile:
            json.dump(questionsJson, tempfile, indent = 4)

        shutil.move(tempfile.name, QUESTIONS_FILE_NAME)

    def addQuestion(self, userID, qID, questionText, correctAnswer = ""):
        for q in self.questionList:
            if qID == q.qID:
                return False
        
        self.questionList.append(Question(userID, qID, questionText, correctAnswer))
        for q in self.questionList:
            print(vars(q))

        #save new data
        self.writeQuestionsToFile()
        return True

    def removeQuestion(self, qID):
        for q in self.questionList:
            if qID == q.qID:
                self.questionList.remove(q)
                
                #save new data
                self.writeQuestionsToFile()
                return True
        return False

    def getQuestionByID(self, qID):
        for q in self.questionList:
            if qID == q.qID:
                return q

        return None

    def getSubmitterByQID(self, qID):
        q = self.getQuestionByID(qID)
        if q:
            return q.userID
        else:
            return None

    def checkAnswer(self, userID, qID, inputAnswer):
        q = self.getQuestionByID(qID)
        if q and q.published:
            if userID in q.answeredBy:
                return "already answered"

            if userID in q.guesses:
                q.guesses[userID] += 1
            else:
                q.guesses[userID] = 1


            if q.guesses[userID] >= MAX_GUESSES + 1:
                self.writeQuestionsToFile()
                return "max guesses"
            elif q.correctAnswer == "":
                self.writeQuestionsToFile()
                return "needsManual"
            elif q.checkAnswer(userID, inputAnswer):
                self.writeQuestionsToFile()
                return "correct"

            self.writeQuestionsToFile()
            return "incorrect"
        return "notFound"

    def listQuestions(self):
        output = ""
        for q in self.questionList:
            if q.published:
                output += q.prettyPrint() + "\n"
        return output

    def expireQuestions(self):
        questionsExpired = []
        for q in self.questionList:
            if q.timeToExpire():
                questionsExpired.append(q.qID)
                self.questionList.remove(q)
        self.writeQuestionsToFile()

        return questionsExpired

    def publishByID(self, qID):
        q = self.getQuestionByID(qID)
        if q:
            if q.publish():
                self.writeQuestionsToFile()
                return "published"
            else:
                return "already published"
        else:
            return "notFound"

    def publishAllByUser(self, userID):
        for q in self.questionList:
            if q.userID == userID:
                q.publish()
        self.writeQuestionsToFile()

    def firstTimeDisplay(self):
        output = ""
        for q in self.questionList:
            if q.justPublished:
                q.justPublished = False
                output += q.prettyPrint() + "\n"
        return output



