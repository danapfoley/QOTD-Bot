import time
import json
from tempfile import NamedTemporaryFile
import shutil

MAX_GUESSES = 3

QUESTIONS_FILE_NAME = "questions.json"
OLD_QUESTIONS_FILE_NAME = "questionsHistory.json"

def splitCategory(qID):
    #Splitting the category from qID.
    #Current format is: "Category"qID
    firstInst, lastInst = qID.find('"'), qID.rfind('"')
    category = ""
    if qID.count('"') == 2 and firstInst == 0 and lastInst != (len(qID) - 1):
        category = qID[1:lastInst]
        qID = qID[lastInst+1:]
    return qID, category


class Question:
    def __init__(self, userID, qID, questionText, correctAnswer = "", category = ""):
        self.userID = userID
        self.qID = qID
        self.questionText = questionText
        self.correctAnswer = correctAnswer
        self.category = category
        self.initTime = time.time()
        self.publishTime = 0
        self.expireTime = 0
        self.published = False
        self.justPublished = False
        self.answeredBy = []
        self.guesses = {}
        
    def cleanUpAnswer(self, answer):
        answer = answer.lower().strip()
        words = answer.split(' ')
        removeWords = ["a","an","the"]
        removeChars = ["'", "’", "-", ",", ".", "?", "\"", "/", "[", "]", "(", ")", "`", "~"]

        strippedWords = [word for word in words if word not in removeWords]
        answer = ' '.join(strippedWords).strip()

        for char in removeChars:
            answer = answer.replace(char, "")

        return answer

    def checkAnswer(self, userID, inputAnswer):
        match = self.cleanUpAnswer(self.correctAnswer) == self.cleanUpAnswer(inputAnswer)
        if match and userID not in self.answeredBy:
            self.answeredBy.append(userID)
        return match

    def timeToExpire(self):
        return (time.time() - self.publishTime) > 60 * 60 * 18

    def prettyPrint(self):
        output = "" if self.category == "" else (self.category + " ")
        output = output + "(" + self.qID + "): " + self.questionText
        return output

    def prettyPrintWithAnswer(self):
        return self.prettyPrint() + " : " + self.correctAnswer

    def countAnswers(self):
        return len(self.answeredBy)
    
    def countGuesses(self):
        return len(self.guesses)

    def publish(self):
        if self.published:
            return False
        else:
            self.published = True
            self.justPublished = True
            self.publishTime = time.time()
            return True

class QuestionKeeper:
    def __init__(self):
        self.questionList = []
        self.loadQuestionsFromFile()

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
                q = Question(qJson["userID"], qJson["qID"], qJson["questionText"], qJson["correctAnswer"], qJson["category"])
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

    def writeRemovedQuestionsToFile(self, removedQuestionsList):
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
        with open(QUESTIONS_FILE_NAME, 'w') as tempfile:
            json.dump(questionsJson, tempfile, indent = 4)

        shutil.move(tempfile.name, OLD_QUESTIONS_FILE_NAME)

    def addQuestion(self, userID, qID, questionText, correctAnswer = ""):
        qID, category = splitCategory(qID)

        for q in self.questionList:
            if qID.lower() == q.qID.lower():
                return False
        
        self.questionList.append(Question(userID, qID, questionText, correctAnswer, category))

        #save new data
        self.writeQuestionsToFile()
        return True

    def removeQuestion(self, qID, userID):
        qID, category = splitCategory(qID)

        for q in self.questionList:
            if qID.lower() == q.qID.lower() and (q.userID == userID or userID == "DEV"):
                self.questionList.remove(q)
                
                #save new data
                self.writeQuestionsToFile()
                return True
        return False

    def getQuestionByID(self, qID):
        qID, category = splitCategory(qID)

        for q in self.questionList:
            if qID.lower() == q.qID.lower():
                return q

        return None

    def getUserQuestionByID(self, qID, userID):
        qID, category = splitCategory(qID)

        for q in self.questionList:
            if qID.lower() == q.qID.lower() and (q.userID == userID or userID == "DEV"):
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
    
    def listQuestionsPrivate(self, userID):
        output = ""
        for q in self.questionList:
            if q.published:
                if userID not in q.answeredBy \
                  and userID != q.userID\
                  and (userID not in q.guesses or q.guesses[userID] < MAX_GUESSES):
                    output += "● "
                output += q.prettyPrint() + "\n"
        return output

    def listQuestionsByUser(self, userID):
        output = ""
        for q in self.questionList:
            if q.userID == userID:
                output += q.prettyPrintWithAnswer() + (" (published)" if q.published else "") + "\n"
        return output

    def expireQuestions(self, userID):
        questionsExpired = []
        for q in self.questionList:
            if q.timeToExpire() and q.userID == userID:
                q.expireTime = time.time()
                questionsExpired.append(q)

        self.questionList = [q for q in self.questionList if q not in questionsExpired]
        questionsExpiredStrings = [q.prettyPrintWithAnswer() for q in questionsExpired]
        
        self.writeQuestionsToFile()
        self.writeRemovedQuestionsToFile(questionsExpired)

        return questionsExpiredStrings

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
        self.writeQuestionsToFile()
        return output

    def getOldQuestionsString(self):
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
        elapsedTime = 60 * 60 * 24 #24 hours
        response = ""

        for q in oldQuestions["oldQuestions"]:
            #Questions are inserted at the beginning of the data
            #So it's sorted newer to older
            #Thus if we hit a question older than 24hrs, we can stop searching
            if (now - q["expireTime"]) > elapsedTime:
                break
            response += "" if q["category"] == "" else (q["category"] + " ")
            response += "(" + q["qID"] + "): " + q["questionText"] + " : " + q["correctAnswer"]

            response += "\n"

        return response



