import csv
from tempfile import NamedTemporaryFile
import shutil
from datetime import date, datetime, timedelta

class ScoreKeeper:
    def __init__(self):
        self.fileName = "scores.csv"
        self.data = []
        self.todayRowNum = -1 #error value
        self.totalsRowNum = 2 #manually set
        self.userIDRowNum = 0 #manually set
        self.userNameRowNum = 1 #manually set

        self.catchUpDateRows()
        self.getDataFromFile()

    def getTodayScores(self):
        scoresList = []
        todayScores = self.data[self.todayRowNum]
        for column, score in enumerate(todayScores):
            if column == 0:
                continue
            if score != "":
                 scoresList.append(self.data[self.userNameRowNum][column] + " - " + str(score))
        if len(scoresList) > 0:
            return "Today's scores: " + ", ".join(scoresList) + "\n"
        else:
            return "No new scores from today.\n"

    def getTotalScores(self):
        scoresList = []
        totalScores = self.data[self.totalsRowNum]
        for column, score in enumerate(totalScores):
            if column == 0:
                continue
            if score != "":
                 scoresList.append(self.data[self.userNameRowNum][column] + " - " + str(score))
        
        return "Total scores: " + ", ".join(scoresList)
        
    def updateFileWithData(self):
        tempfile = NamedTemporaryFile(delete=False)
        with open(self.fileName, 'w', newline='') as tempfile:
            writer = csv.writer(tempfile)

            for row in self.data:
                writer.writerow(row)

        shutil.move(tempfile.name, self.fileName)


    def catchUpDateRows(self):
        file = open(self.fileName,"r")
        reader = list(csv.reader(file))
        file.close()
        
        numRows = len(reader)
        rowLength = len(reader[0])

        today = datetime.today().date()
        lastDate = datetime.strptime(reader[-1][0], "%m/%d/%Y").date()
        newData=[]
        if lastDate < today:
            needsCatchUp = True
        else:
            needsCatchUp = False

        while lastDate < today:
            lastDate += timedelta(days=1)
            numRows += 1
            newData.append([lastDate.strftime("%m/%d/%Y")] + ([""] * rowLength))

        if needsCatchUp:
            file = open(self.fileName, "a", newline='')
            writer = csv.writer(file)
            writer.writerows(newData)
            file.close()

        self.todayRowNum = numRows - 1
        
    def userExists(self, userID):
        return userID in self.data[self.userIDRowNum]

    def getUserColumnNum(self, userID):
        if userID in self.data[self.userIDRowNum]:
            return self.data[self.userIDRowNum].index(userID)
        else:
            return -1

    def addNewUser(self, userID):
        for idx, row in enumerate(self.data):
            self.data[idx].append("")
        self.data[self.totalsRowNum][-1] = 0
        self.data[self.userIDRowNum][-1] = userID

    def addNameToUser(self, userID, userName):
        columnNum = self.getUserColumnNum(userID)
        self.data[self.userNameRowNum][columnNum] = userName

    def addUserPoint(self, userID):
        self.addUserPoints(userID, 1)

    def addUserPoints(self, userID, numPoints):
        columnNum = self.getUserColumnNum(userID)
        if columnNum == -1:
            self.addNewUser(userID)
            columnNum = self.getUserColumnNum(userID)
        if self.data[self.todayRowNum][columnNum] == "":
            self.data[self.todayRowNum][columnNum] = 0

        self.data[self.todayRowNum][columnNum]  = int(self.data[self.todayRowNum][columnNum]) + numPoints
        self.data[self.totalsRowNum][columnNum] = int(self.data[self.totalsRowNum][columnNum]) + numPoints
        self.updateFileWithData()

    def getDataFromFile(self):
        file = open(self.fileName,"r")
        self.data = list(csv.reader(file))
        file.close()


