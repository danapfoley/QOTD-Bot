import time

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

    def addQuestion(self, userID, qID, questionText, correctAnswer = ""):
        for q in self.questionList:
            if qID == q.qID:
                return False
        
        self.questionList.append(Question(userID, qID, questionText, correctAnswer))
        return True

    def removeQuestion(self, qID):
        for q in self.questionList:
            if qID == q.qID:
                self.questionList.remove(q)
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
            elif q.correctAnswer == "":
                return "needsManual"
            elif q.checkAnswer(userID, inputAnswer):
                return "correct"
            return "incorrect"
        return "notFound"

    def listQuestions(self):
        output = ""
        for q in self.questionList:
            if q.published:
                output += q.prettyPrint() + "\n"
        return output

    def publishByID(self, qID):
        q = self.getQuestionByID(qID)
        if q:
            if q.publish():
                return "published"
            else:
                return "already published"
        else:
            return "notFound"

    def publishAllByUser(self, userID):
        for q in self.questionList:
            if q.userID == userID:
                q.publish()

    def firstTimeDisplay(self):
        output = ""
        for q in self.questionList:
            if q.justPublished:
                q.justPublished = False
                output += q.prettyPrint() + "\n"
        return output



