import time

class Question:
    def __init__(self, userID, qID, questionText, correctAnswer = ""):
        self.userID = userID
        self.qID = qID
        self.questionText = questionText
        self.correctAnswer = correctAnswer
        self.initTime = time.time()

    def checkAnswer(self, inputAnswer):
        return self.correctAnswer.lower() == inputAnswer.lower()

    def timeToExpire(self):
        return (time.time() - self.initTime) > 86400 #seconds in a day

class QuestionKeeper:
    def __init__(self):
        self.questionList = []

    def addQuestion(self, userID, qID, questionText, correctAnswer = ""):
        self.questionList.append(Question(userID, qID, questionText, correctAnswer))
